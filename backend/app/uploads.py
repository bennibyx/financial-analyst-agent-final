from pathlib import Path

from fastapi import UploadFile

from app.config import settings


UPLOAD_DIR = Path(settings.upload_dir)


def save_upload(file: UploadFile) -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    destination = UPLOAD_DIR / Path(file.filename or "uploaded_file").name

    with destination.open("wb") as buffer:
        while chunk := file.file.read(1024 * 1024):
            buffer.write(chunk)

    return destination
