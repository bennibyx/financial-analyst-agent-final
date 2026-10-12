"""POST /brief/{document_id}: one-click analyst brief (JSON + Markdown).
Built by code from the agents' verified outputs; cached in memory per document content."""
import asyncio
import hashlib
import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api_contract import ApiError
from app.database import get_db
from app.models import Document

logger = logging.getLogger(__name__)
router = APIRouter()

# The server runs from backend/, but the agents live in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BRIEF_TIMEOUT_S = 240.0   # extraction + analysis take roughly 30 s; the free host is slower
_CACHE: dict = {}         # (document id, content hash) -> brief; cleared on restart


def _make_brief(text: str, doc_id: str) -> dict:
    from agents.orchestrator import orchestrate
    from agents.brief import build_brief
    return build_brief(orchestrate(text, question=None, doc_id=doc_id))


@router.post(
    "/brief/{document_id}",
    tags=["analysis"],
    summary="One-click analyst brief for a stored document",
    description="Returns a structured brief plus a ready-to-render Markdown version: headline metrics, guidance, "
                "tone, top risks with source quotes and verification notes. Results are cached; add ?refresh=true to rebuild.",
)
async def make_brief(document_id: int, refresh: bool = False, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "document_not_found", f"No document with id {document_id}.")
    if not doc.content or not doc.content.strip():
        raise ApiError(400, "empty_file", "This document has no text to analyse.")
    key = (doc.id, hashlib.sha1(doc.content.encode("utf-8", "replace")).hexdigest()[:10])
    if not refresh and key in _CACHE:
        return _CACHE[key]
    try:
        brief = await asyncio.wait_for(
            asyncio.to_thread(_make_brief, doc.content, str(doc.id)), timeout=BRIEF_TIMEOUT_S)
    except asyncio.TimeoutError:
        raise ApiError(504, "brief_timeout", "Building the brief took too long. Please try again.")
    except Exception:
        logger.exception("Brief failed for document %s", doc.id)
        raise ApiError(500, "internal_error", "The brief could not be generated.")
    _CACHE[key] = brief
    return brief
