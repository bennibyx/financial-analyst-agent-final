import re
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from app.config import settings
from app.extractor import extract_financial_metrics
from app.parser import extract_text, parse_sec_filing, parse_transcript
from app.uploads import save_upload


app = FastAPI(
    title="Autonomous Financial Analyst & Earnings Call Intelligence API",
    version="0.1.0",
    description="Backend: document upload, parsing, storage and agent endpoints.",
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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))