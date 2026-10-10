"""Ingestion API v1: /upload (full pipeline), /documents, /documents/{id}."""
import hashlib
import logging
import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api_contract import (
    ApiError, DocStatus, DocType, DocumentList, DocumentOut,
    ErrorResponse, UploadResponse,
)
from app.config import settings
from app.database import Base, engine, get_db
from app.ingestion.service import persist_document
from app.models import Company, Document
from app.parser import extract_text
from app.uploads import save_upload

logger = logging.getLogger(__name__)
router = APIRouter()

# Creates any missing tables; never alters tables that already exist.
Base.metadata.create_all(bind=engine)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}
KNOWN_COMPANIES = {"nvidia": ("NVIDIA", "NVDA")}  # add more as you go


def _guess_doc_type(filename: str) -> DocType:
    n = filename.lower()
    if "10k" in n or "10-k" in n:
        return DocType.form_10k
    if "10q" in n or "10-q" in n:
        return DocType.form_10q
    if "cfo" in n or "commentary" in n:
        return DocType.commentary
    return DocType.transcript


def _guess_quarter(filename: str) -> str | None:
    m = re.search(r"(q[1-4])[\s_-]?(fy\d{2,4})", filename, flags=re.IGNORECASE)
    return f"{m.group(1).upper()} {m.group(2).upper()}" if m else None


def _guess_company(filename: str) -> tuple[str, str | None]:
    token = re.split(r"[_\-\s.]", filename)[0] or "unknown"
    return KNOWN_COMPANIES.get(token.lower(), (token.title(), None))


def _get_or_create_company(db: Session, name: str, ticker: str | None) -> Company:
    company = None
    if ticker:
        company = db.scalar(select(Company).where(Company.ticker == ticker))
    if company is None:
        company = db.scalar(
            select(Company).where(func.lower(Company.name) == name.lower())
        )
    if company is None:
        company = Company(name=name, ticker=ticker)
        db.add(company)
        db.commit()
        db.refresh(company)
    return company


def _doc_type_of(doc: Document) -> DocType:
    try:
        return DocType(doc.document_type)
    except ValueError:
        return DocType.transcript


def _status_of(doc: Document) -> DocStatus:
    return DocStatus.indexed if doc.chunks else DocStatus.failed


def _to_out(doc: Document) -> DocumentOut:
    status = _status_of(doc)
    return DocumentOut(
        document_id=doc.id,
        filename=doc.filename,
        company=doc.company.name if doc.company else None,
        quarter=_guess_quarter(doc.filename),
        doc_type=_doc_type_of(doc),
        status=status,
        chunk_count=len(doc.chunks),
        error_message=None if status == DocStatus.indexed
        else "No text could be extracted from this document.",
        created_at=doc.uploaded_at,
    )


@router.post(
    "/upload",
    response_model=UploadResponse,
    tags=["ingestion"],
    summary="Upload a document and run the full ingestion pipeline",
    description="Validates the file, parses it, chunks it and stores it. "
    "Re-uploading an identical file returns the existing document with duplicate=true.",
    responses={
        400: {"model": ErrorResponse, "description": "empty_file"},
        413: {"model": ErrorResponse, "description": "file_too_large"},
        415: {"model": ErrorResponse, "description": "unsupported_file_type"},
        422: {"model": ErrorResponse, "description": "parse_failed / no_text_extracted"},
    },
)
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = Path(file.filename or "uploaded_file").name
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ApiError(415, "unsupported_file_type",
                       "Only PDF, TXT and HTML files are supported.")

    data = file.file.read()
    if not data:
        raise ApiError(400, "empty_file", "The uploaded file is empty.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise ApiError(413, "file_too_large",
                       f"File is larger than {settings.max_upload_mb} MB.")

    marker = "sha256:" + hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Document).where(Document.source == marker))
    if existing:
        return UploadResponse(
            document_id=existing.id, filename=existing.filename,
            doc_type=_doc_type_of(existing), status=_status_of(existing),
            duplicate=True,
        )

    file.file.seek(0)
    saved_path = save_upload(file)
    try:
        text = extract_text(saved_path)
    except Exception as exc:
        logger.exception("Parsing failed for %s", filename)
        raise ApiError(422, "parse_failed", f"Could not read this file: {exc}")
    if not text or not text.strip():
        raise ApiError(422, "no_text_extracted",
                       "No text could be extracted (is this a scanned PDF?).")

    name, ticker = _guess_company(filename)
    company = _get_or_create_company(db, name, ticker)
    doc_type = _guess_doc_type(filename)
    try:
        document = persist_document(
            db, company_id=company.id, filename=filename, content=text,
            document_type=doc_type.value, source=marker,
        )
    except Exception:
        db.rollback()
        logger.exception("Persisting %s failed", filename)
        raise ApiError(500, "ingestion_failed", "Could not store the document.")

    return UploadResponse(
        document_id=document.id, filename=document.filename,
        doc_type=doc_type, status=_status_of(document), duplicate=False,
    )


@router.get("/documents", response_model=DocumentList, tags=["documents"],
            summary="List all documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).order_by(Document.id.desc())).all()
    return DocumentList(items=[_to_out(d) for d in docs], total=len(docs))


@router.get("/documents/{document_id}", response_model=DocumentOut,
            tags=["documents"], summary="Get one document and its status",
            responses={404: {"model": ErrorResponse}})
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise ApiError(404, "document_not_found", "Document not found.")
    return _to_out(doc)
