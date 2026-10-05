from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException

from app.config import settings
from app.uploads import save_upload
from app.parser import extract_text, parse_transcript
from app.extractor import extract_financial_metrics


app = FastAPI(
    title="Autonomous Financial Analyst & Earnings Call Intelligence API",
    version="0.1.0",
    description="Backend: document upload, parsing, storage and agent endpoints.",
)


ALLOWED_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}


@app.get("/health", tags=["system"])
def health():
    """Liveness check used by Docker, the hosting platform and the team."""

    return {
        "status": "ok",
        "service": "financial-analyst-api",
        "version": app.version,
        "nebius_key_configured": bool(settings.nebius_api_key),
    }


@app.post("/upload", tags=["documents"])
def upload_document(file: UploadFile = File(...)):
    """Upload a PDF, TXT, or HTML document for later parsing and analysis."""

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF, TXT, and HTML files are allowed.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit",
        )

    saved_path = save_upload(file)

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size_bytes": size,
        "file_type": extension,
        "path": str(saved_path),
    }


@app.post("/parse", tags=["documents"])
def parse_document(file: UploadFile = File(...)):
    """Upload and parse an earnings-call transcript."""

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF, TXT, and HTML files are allowed.",
        )

    max_bytes = settings.max_upload_mb * 1024 * 1024

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {settings.max_upload_mb} MB limit",
        )

    saved_path = save_upload(file)

    try:
        # Extract raw text from the uploaded document
        text = extract_text(saved_path)

        # Parse transcript into prepared remarks, Q&A, and speakers
        parsed = parse_transcript(text)

        # Extract financial metrics from the full document
        metrics = extract_financial_metrics(text)

    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unable to parse document: {exc}",
        )

    return {
        "status": "parsed",
        "filename": file.filename,
        "size_bytes": size,
        "file_type": extension,
        "parsed": parsed,
        "metrics": metrics,
    }