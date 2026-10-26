import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import ingestion_api, uploads
from app.database import Base, get_db
from app.main import app


@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'upload-tests.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with TestingSessionLocal() as db:
            yield db

    upload_dir = tmp_path / "uploads"
    monkeypatch.setattr(uploads, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(ingestion_api.settings, "max_upload_mb", 1)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, upload_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_empty_upload_returns_structured_400(upload_client):
    client, _ = upload_client

    response = client.post(
        "/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_file"


def test_oversized_upload_returns_structured_413(upload_client):
    client, _ = upload_client

    response = client.post(
        "/upload",
        files={"file": ("large.txt", b"x" * (1024 * 1024 + 1), "text/plain")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_unsupported_extension_returns_structured_415(upload_client):
    client, _ = upload_client

    response = client.post(
        "/upload",
        files={"file": ("payload.exe", b"not executable", "application/octet-stream")},
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_corrupt_pdf_returns_parse_failed_and_cleans_upload(
    upload_client,
):
    client, upload_dir = upload_client

    response = client.post(
        "/upload",
        files={"file": ("corrupt.pdf", b"this is not a PDF", "application/pdf")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "parse_failed"
    assert not list(upload_dir.glob("*"))


def test_document_without_extractable_text_is_rejected_and_cleaned(
    upload_client, monkeypatch,
):
    client, upload_dir = upload_client
    monkeypatch.setattr(ingestion_api, "extract_text", lambda path: "   ")

    response = client.post(
        "/upload",
        files={"file": ("blank.txt", b"valid upload bytes", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_text_extracted"
    assert not list(upload_dir.glob("*"))
