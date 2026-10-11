"""POST /extract/{document_id}: runs the Extraction Agent on a stored document."""
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api_contract import ApiError, ErrorResponse
from app.database import get_db
from app.ingestion_api import _doc_type_of, _guess_quarter
from app.models import Document, Metric

logger = logging.getLogger(__name__)
router = APIRouter()

# The server runs from backend/, but the agents live in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXTRACT_TIMEOUT_S = 120.0


class MetricOut(BaseModel):
    name: str = Field(..., examples=["revenue"])
    basis: Optional[str] = Field(None, examples=["GAAP"])
    value: Optional[float] = Field(None, examples=[1000.0])
    unit: str = Field(..., examples=["USD_million"])
    period: str = Field(..., examples=["Q2 FY27"])
    yoy_change_pct: Optional[float] = None
    qoq_change_pct: Optional[float] = None
    source_quote: str


class GuidanceOut(BaseModel):
    metric: str
    period: str
    basis: Optional[str] = None
    low: Optional[float] = None
    high: Optional[float] = None
    midpoint: Optional[float] = None
    range_pct: Optional[float] = None
    unit: str
    qualitative: Optional[str] = None
    source_quote: str


class ExtractResponse(BaseModel):
    document_id: int
    company: Optional[str] = None
    period: Optional[str] = None
    doc_type: str
    stub: bool = Field(False, description="True only when ?sample=true is used (fake sample data).")
    metrics: list[MetricOut]
    guidance: list[GuidanceOut] = []
    saved_to_db: int = Field(0, description="How many metrics with a value were saved to the database.")
    issues: list[str] = Field(
        [], description="Problems found by the agent's verification checks (e.g. a quote not found in the source)."
    )


def _sample_response(doc: Document, period: str) -> ExtractResponse:
    sample = "SAMPLE DATA (stub): not a real figure."
    return ExtractResponse(
        document_id=doc.id,
        company=doc.company.name if doc.company else None,
        period=period,
        doc_type=_doc_type_of(doc).value,
        stub=True,
        metrics=[
            MetricOut(name="revenue", basis="GAAP", value=1000.0, unit="USD_million",
                      period=period, yoy_change_pct=10.0, qoq_change_pct=5.0, source_quote=sample),
            MetricOut(name="eps", basis="non-GAAP", value=1.0, unit="USD",
                      period=period, yoy_change_pct=12.0, qoq_change_pct=4.0, source_quote=sample),
            MetricOut(name="gross_margin", basis="non-GAAP", value=70.0, unit="percent",
                      period=period, source_quote=sample),
        ],
        guidance=[
            GuidanceOut(metric="revenue", period="next quarter", basis="GAAP", low=1000.0,
                        high=1100.0, midpoint=1050.0, unit="USD_million", source_quote=sample),
        ],
        issues=[],
    )


def _metric_row_name(m) -> str:
    """Basis is folded into the name because the metrics table has no basis column."""
    if m.basis:
        return f"{m.name}_{m.basis.lower().replace('-', '_')}"
    return m.name


def _save_metrics(db: Session, doc: Document, metrics: list) -> int:
    """Replace this document's stored metrics with the new ones (safe to re-run)."""
    try:
        db.execute(delete(Metric).where(Metric.source_document_id == doc.id))
        rows = [
            Metric(
                company_id=doc.company_id,
                name=_metric_row_name(m),
                value=m.value,
                unit=m.unit,
                period=m.period,
                source_document_id=doc.id,
            )
            for m in metrics
            if m.value is not None
        ]
        db.add_all(rows)
        db.commit()
        return len(rows)
    except Exception:
        db.rollback()
        logger.exception("Could not save metrics for document %s", doc.id)
        return 0


def _as_text(item: Any) -> str:
    return item if isinstance(item, str) else str(item)


@router.post(
    "/extract/{document_id}",
    response_model=ExtractResponse,
    tags=["extraction"],
    summary="Extract key financial metrics from a stored document",
    description="Runs the Extraction Agent on the stored text. Can take 10-60 seconds. "
    "Add ?sample=true to get fast fake sample data in the same shape.",
    responses={
        404: {"model": ErrorResponse, "description": "document_not_found"},
        422: {"model": ErrorResponse, "description": "no_text_content"},
        502: {"model": ErrorResponse, "description": "extraction_failed"},
        504: {"model": ErrorResponse, "description": "extraction_timeout"},
    },
)
async def extract_document(
    document_id: int,
    sample: bool = False,
    force: bool = False,
    db: Session = Depends(get_db),
):
    doc = db.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "document_not_found", "Document not found.")

    period = _guess_quarter(doc.filename) or "Q? FY??"
    if sample:
        return _sample_response(doc, period)

    if not doc.content or not doc.content.strip():
        raise ApiError(422, "no_text_content", "This document has no text to extract from.")

    import hashlib
    import pathlib
    cache_file = pathlib.Path("data/extract_cache") / f"{doc.id}-{hashlib.sha1(doc.content.encode()).hexdigest()[:10]}.json"
    if cache_file.exists() and not force:
        try:
            return ExtractResponse.model_validate_json(cache_file.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Ignoring unreadable extract cache %s", cache_file)

    try:
        from agents.extraction_agent import run_extraction
    except Exception:
        logger.exception("Could not import the extraction agent")
        raise ApiError(500, "agent_unavailable", "The extraction agent could not be loaded.")

    try:
        out = await asyncio.wait_for(
            asyncio.to_thread(run_extraction, doc.content, "auto", str(doc.id)),
            timeout=EXTRACT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Extraction timed out for document %s", doc.id)
        raise ApiError(504, "extraction_timeout",
                       "Extraction took too long. Please try again.")
    except Exception:
        logger.exception("Extraction failed for document %s", doc.id)
        raise ApiError(502, "extraction_failed",
                       "The extraction agent failed on this document.")

    metrics_out = [MetricOut.model_validate(m) for m in out.get("metrics", [])]
    saved = _save_metrics(db, doc, metrics_out)

    try:
        from agents.normalize import normalize_period
        period = normalize_period(period)
    except Exception:
        pass

    response = ExtractResponse(
        document_id=doc.id,
        company=doc.company.name if doc.company else None,
        period=period,
        doc_type=_doc_type_of(doc).value,
        stub=False,
        saved_to_db=saved,
        metrics=metrics_out,
        guidance=[GuidanceOut.model_validate(g) for g in out.get("guidance", [])],
        issues=[_as_text(i) for i in out.get("issues", [])],
    )
    if {"revenue", "net_income", "operating_income", "eps"} <= {m.name for m in response.metrics}:   # cache only complete results
        try:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(response.model_dump_json(), encoding="utf-8")
        except Exception:
            logger.warning("Could not write extract cache %s", cache_file)
    return response


class StoredMetric(BaseModel):
    name: str = Field(..., examples=["gross_margin_non_gaap"])
    value: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None


class StoredMetrics(BaseModel):
    document_id: int
    items: list[StoredMetric]


@router.get(
    "/documents/{document_id}/metrics",
    response_model=StoredMetrics,
    tags=["extraction"],
    summary="Metrics already extracted and saved for a document (fast, no LLM call)",
    description="Empty list until /extract has been run on the document.",
    responses={404: {"model": ErrorResponse, "description": "document_not_found"}},
)
def get_saved_metrics(document_id: int, db: Session = Depends(get_db)):
    if db.get(Document, document_id) is None:
        raise ApiError(404, "document_not_found", "Document not found.")
    rows = db.scalars(
        select(Metric).where(Metric.source_document_id == document_id).order_by(Metric.id)
    ).all()
    return StoredMetrics(
        document_id=document_id,
        items=[StoredMetric(name=r.name, value=r.value, unit=r.unit, period=r.period) for r in rows],
    )
