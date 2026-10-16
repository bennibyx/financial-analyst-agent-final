
from pathlib import Path
import re

from fastapi import UploadFile

from app.config import settings


UPLOAD_DIR = Path(settings.upload_dir)
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".html"}


def save_upload(file: UploadFile) -> Path:
    filename = Path(file.filename or "uploaded_file").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Allowed types: PDF, TXT, HTML."
        )

    # Remove unsafe characters from the filename.
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    if not safe_name or safe_name.startswith("."):
        safe_name = f"upload{extension}"

    max_bytes = settings.max_upload_mb * 1024 * 1024
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Avoid overwriting an existing upload with the same name.
    destination = UPLOAD_DIR / safe_name
    stem = destination.stem
    suffix = destination.suffix
    counter = 1

    while destination.exists():
        destination = UPLOAD_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    size = 0
    try:
        with destination.open("wb") as buffer:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(
                        f"File exceeds the {settings.max_upload_mb} MB limit."
                    )
                buffer.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    return destination
