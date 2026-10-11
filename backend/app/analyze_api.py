"""POST /analyze/{document_id} starts a background job; GET /jobs/{job_id} is polled for status."""
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api_contract import ApiError, DocType, ErrorResponse
from app.database import Base, SessionLocal, engine, get_db
from app.ingestion_api import _doc_type_of
from app.models import Document, Job, Risk

logger = logging.getLogger(__name__)
router = APIRouter()

# The server runs from backend/, but the agents live in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ANALYZE_TIMEOUT_S = 300.0
ALLOWED_TYPES = {DocType.transcript, DocType.commentary}

# Creates any missing tables (such as jobs); never alters existing ones.
Base.metadata.create_all(bind=engine)


def _fail_stale_jobs() -> None:
    """Jobs still queued/running at startup were killed by a restart; mark them failed."""
    db = SessionLocal()
    try:
        db.execute(
            update(Job)
            .where(Job.status.in_(["queued", "running"]))
            .values(
                status="failed",
                error_code="server_restarted",
                error_message="The server restarted while this job was running. Please start it again.",
                finished_at=datetime.utcnow(),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not clean up stale jobs")
    finally:
        db.close()


_fail_stale_jobs()


# ---------- Response models ----------

class JobError(BaseModel):
    code: str = Field(..., examples=["analysis_timeout"])
    message: str


class RiskItemOut(BaseModel):
    category: str
    title: str
    severity: int = Field(..., description="1 (minor) to 5 (major)")
    status: str = Field(..., description="current or potential")
    quantified: bool
    quote: str
    explanation: str


class RiskResultOut(BaseModel):
    overall_risk_level: str = Field(..., examples=["medium"])
    risks: list[RiskItemOut]


class AnalysisResult(BaseModel):
    schema_version: Optional[str] = None
    sentiment: Optional[dict[str, Any]] = Field(
        None, description="Sentiment agent output (null if that agent failed; see errors)."
    )
    risk: Optional[RiskResultOut] = Field(
        None, description="Risk agent output (null if that agent failed; see errors)."
    )
    issues: list[str] = []
    errors: dict[str, str] = {}


class JobOut(BaseModel):
    job_id: int
    document_id: int
    kind: str = "analyze"
    status: Literal["queued", "running", "done", "failed"]
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[JobError] = Field(None, description="Only set when status is 'failed'.")
    result: Optional[AnalysisResult] = Field(None, description="Only set when status is 'done'.")


def _to_job_out(job: Job) -> JobOut:
    result = None
    if job.status == "done" and job.result_json:
        try:
            result = AnalysisResult.model_validate(json.loads(job.result_json))
        except Exception:
            logger.exception("Could not read stored result for job %s", job.id)
    error = None
    if job.status == "failed":
        error = JobError(code=job.error_code or "unknown", message=job.error_message or "")
    return JobOut(
        job_id=job.id, document_id=job.document_id, kind=job.kind, status=job.status,
        created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at,
        error=error, result=result,
    )


# ---------- Background work ----------

def _fail(db: Session, job: Job, code: str, message: str) -> None:
    job.status = "failed"
    job.error_code = code
    job.error_message = message[:1000]
    job.finished_at = datetime.utcnow()
    db.commit()


def _save_risks(db: Session, doc: Document, risk: Optional[dict]) -> None:
    """Replace this document's stored risks. Skipped if the risk agent produced nothing."""
    if not risk:
        return
    try:
        db.execute(delete(Risk).where(Risk.source_document_id == doc.id))
        rows = []
        for r in risk.get("risks", []):
            title = r.get("title", "")
            explanation = r.get("explanation", "")
            rows.append(
                Risk(
                    company_id=doc.company_id,
                    category=r.get("category", "other"),
                    description=f"{title}: {explanation}".strip(": "),
                    severity=str(r.get("severity")),
                    source_document_id=doc.id,
                )
            )
        db.add_all(rows)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not save risks for document %s", doc.id)


def _run_agents(text: str) -> dict:
    """Runs sentiment and risk separately so one failing never kills the other.
    Accepts both return shapes of analyze_sentiment: (Sentiment, retries) or {"result": ...}."""
    from agents.risk import analyze_risk
    from agents.sentiment import analyze_sentiment

    out = {"schema_version": "1.1", "sentiment": None, "risk": None, "issues": [], "errors": {}}

    try:
        res = analyze_sentiment(text)
        if isinstance(res, tuple):
            res = res[0]
        if isinstance(res, dict) and "result" in res:
            out["issues"] += [f"sentiment: {i}" for i in res.get("issues", [])]
            res = res["result"]
        out["sentiment"] = res.model_dump() if hasattr(res, "model_dump") else res
    except Exception as e:
        logger.exception("Sentiment agent failed")
        out["errors"]["sentiment"] = str(e)[:300]

    try:
        res = analyze_risk(text)
        out["issues"] += [f"risk: {i}" for i in res.get("issues", [])]
        out["risk"] = res["result"]
    except Exception as e:
        logger.exception("Risk agent failed")
        out["errors"]["risk"] = str(e)[:300]

    return out


def _run_job(job_id: int) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if job is None:
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        doc = db.get(Document, job.document_id)

        try:
            from agents.risk import analyze_risk  # noqa: F401 (availability check)
            from agents.sentiment import analyze_sentiment  # noqa: F401
        except Exception:
            logger.exception("Could not import the analysis agent")
            _fail(db, job, "agent_unavailable", "The analysis agent could not be loaded.")
            return

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_run_agents, doc.content)
        try:
            out = future.result(timeout=ANALYZE_TIMEOUT_S)
        except FutureTimeout:
            executor.shutdown(wait=False)
            logger.warning("Analysis timed out for document %s", doc.id)
            _fail(db, job, "analysis_timeout", "Analysis took too long. Please try again.")
            return
        except Exception:
            executor.shutdown(wait=False)
            logger.exception("Analysis failed for document %s", doc.id)
            _fail(db, job, "analysis_failed", "The analysis agent failed on this document.")
            return
        executor.shutdown(wait=False)

        if out.get("sentiment") is None and out.get("risk") is None:
            detail = "; ".join(f"{k}: {v}" for k, v in out.get("errors", {}).items())
            _fail(db, job, "analysis_failed", detail or "Both agents returned nothing.")
            return

        _save_risks(db, doc, out.get("risk"))
        job.result_json = json.dumps(out, default=str)
        job.status = "done"
        job.finished_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Job %s crashed", job_id)
        try:
            job = db.get(Job, job_id)
            if job is not None:
                _fail(db, job, "internal_error", "Something went wrong on our side.")
        except Exception:
            logger.exception("Could not mark job %s as failed", job_id)
    finally:
        db.close()


# ---------- Endpoints ----------

@router.post(
    "/analyze/{document_id}",
    response_model=JobOut,
    status_code=202,
    tags=["analysis"],
    summary="Start risk and sentiment analysis (background job)",
    description="Returns immediately with a job_id and status 'queued'. Poll GET /jobs/{job_id} "
    "until status is 'done' or 'failed'. Supports transcripts and CFO commentary. "
    "If a job is already queued or running for this document, that job is returned instead.",
    responses={
        404: {"model": ErrorResponse, "description": "document_not_found"},
        422: {"model": ErrorResponse, "description": "unsupported_doc_type / no_text_content"},
    },
)
def start_analysis(
    document_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "document_not_found", "Document not found.")
    if _doc_type_of(doc) not in ALLOWED_TYPES:
        raise ApiError(
            422, "unsupported_doc_type",
            "Risk and sentiment analysis supports earnings-call transcripts and CFO commentary, not filings.",
        )
    if not doc.content or not doc.content.strip():
        raise ApiError(422, "no_text_content", "This document has no text to analyze.")

    active = db.scalar(
        select(Job)
        .where(Job.document_id == doc.id, Job.kind == "analyze",
               Job.status.in_(["queued", "running"]))
        .order_by(Job.id.desc())
    )
    if active:
        return _to_job_out(active)

    job = Job(document_id=doc.id, kind="analyze", status="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    background.add_task(_run_job, job.id)
    return _to_job_out(job)


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
    tags=["analysis"],
    summary="Check a background job (poll every 2-3 seconds)",
    responses={404: {"model": ErrorResponse, "description": "job_not_found"}},
)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None:
        raise ApiError(404, "job_not_found", "Job not found.")
    return _to_job_out(job)


@router.get(
    "/documents/{document_id}/analysis",
    response_model=JobOut,
    tags=["analysis"],
    summary="Latest finished analysis for a document (fast, no LLM call)",
    responses={404: {"model": ErrorResponse, "description": "document_not_found / analysis_not_found"}},
)
def latest_analysis(document_id: int, db: Session = Depends(get_db)):
    if db.get(Document, document_id) is None:
        raise ApiError(404, "document_not_found", "Document not found.")
    job = db.scalar(
        select(Job)
        .where(Job.document_id == document_id, Job.kind == "analyze", Job.status == "done")
        .order_by(Job.id.desc())
    )
    if job is None:
        raise ApiError(404, "analysis_not_found",
                       "No completed analysis for this document yet. Start one with POST /analyze/{id}.")
    return _to_job_out(job)
