
import asyncio
import logging
import re
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.extractor import extract_financial_metrics
from app.ingestion.service import persist_document
from app.models import Document
from app.parser import extract_text, parse_sec_filing, parse_transcript
from app.schemas import AskRequest, AnalystAnswerResponse
from app.uploads import save_upload

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous Financial Analyst & Earnings Call Intelligence API",
    version="0.1.0",
    description="Backend: document upload, parsing, storage and agent endpoints.",
)


ASK_FALLBACK = (
    "This is a sample response from the Financial Analyst Agent. "
    "Document-based question answering is temporarily unavailable. "
    "Please try again later."
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "financial-analyst-api",
        "version": "0.1.0",
        "nebius_key_configured": bool(settings.nebius_api_key),
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    try:
        saved_path = save_upload(file)
        return {
            "status": "uploaded",
            "filename": saved_path.name,
            "path": str(saved_path),
            "size_bytes": saved_path.stat().st_size,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/parse")
async def parse_document(file: UploadFile = File(...)):
    try:
        saved_path = save_upload(file)
        extension = saved_path.suffix.lower()

        text = extract_text(saved_path)

        # SEC filings can be PDF, TXT, or HTML.
        # Detect them by their Item headings rather than file extension.
        if re.search(
            r"\bitem\s+1[\.\s]+business\b"
            r"|\bitem\s+1a[\.\s]+risk\s+factors\b"
            r"|\bitem\s+7[\.\s]+management",
            text,
            flags=re.IGNORECASE,
        ):
            parsed = parse_sec_filing(text)
        else:
            parsed = parse_transcript(text)

        metrics = extract_financial_metrics(text)

        return {
            "status": "parsed",
            "filename": saved_path.name,
            "size_bytes": saved_path.stat().st_size,
            "file_type": extension,
            "parsed": parsed,
            "metrics": metrics,
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/ingest")
async def ingest_document(
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        saved_path = save_upload(file)
        text = extract_text(saved_path)

        document = persist_document(
            db,
            company_id=company_id,
            filename=saved_path.name,
            content=text,
        )

        return {
            "status": "ingested",
            "document_id": document.id,
            "filename": document.filename,
            "chunk_count": len(document.chunks),
        }

    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Document ingestion failed")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ask", response_model=AnalystAnswerResponse)
async def ask_document_question(
    request: AskRequest,
    db: Session = Depends(get_db),
):
    # The database uses integer document IDs.
    try:
        document_id = int(request.document_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="document_id must be a numeric document ID",
        )

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if not document.content or not document.content.strip():
        raise HTTPException(
            status_code=422,
            detail="Document has no text content",
        )

    try:
        # Lazy import prevents agent configuration problems from
        # preventing the FastAPI application from starting.
        from agents.analyst import answer_question

        agent_output = await asyncio.wait_for(
            asyncio.to_thread(
                answer_question,
                request.question,
                document.content,
                doc_id=str(document.id),
            ),
            timeout=90.0,
        )

        result = agent_output.get("result", {})

        return AnalystAnswerResponse(
            answer=result.get("answer", ASK_FALLBACK),
            citations=result.get("citations", []),
        )

    except asyncio.TimeoutError:
        logger.warning("The /ask agent timed out after 90 seconds")

    except Exception:
        logger.exception("The /ask agent failed")

    # Return the sample response if the agent fails or times out.
    return AnalystAnswerResponse(
        answer=ASK_FALLBACK,
        citations=[],
    )