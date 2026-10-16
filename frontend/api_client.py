
"""Frontend API client for the Financial Analyst Agent.

Supports raw uploads, full document ingestion, real risk/sentiment
analysis jobs, and the existing mock dashboard/chat functions.
"""

import json
import os
from pathlib import Path

import requests


API_BASE_URL = os.getenv(
    "FINANCIAL_ANALYST_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

_MOCK_FILE = Path(__file__).parent / "mock_analysis.json"
REQUEST_TIMEOUT = 60
INGEST_TIMEOUT = 120


def _error_detail(response, default_message):
    """Extract a useful error message from backend responses."""
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                return error.get("message") or error.get("code") or default_message

            return data.get("detail") or data.get("message") or default_message
    except (ValueError, requests.JSONDecodeError):
        pass

    return default_message


def _post_file(endpoint, uploaded_file, timeout):
    """POST a Streamlit UploadedFile as multipart form data."""
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}{endpoint}",
            files=files,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)

        if getattr(exc, "response", None) is not None:
            detail = _error_detail(exc.response, detail)

        raise RuntimeError(detail) from exc
    except ValueError as exc:
        raise RuntimeError("The backend returned an invalid JSON response.") from exc


def upload_document(uploaded_file):
    """Save a raw upload without creating a database document.

    Kept for compatibility with the existing Day 9 upload workflow.
    Use ingest_document() when the document must be analyzed.
    """
    return _post_file("/upload-raw", uploaded_file, REQUEST_TIMEOUT)


def ingest_document(uploaded_file):
    """Parse, chunk, and persist a document in the backend database.

    Returns a response containing document_id, status, and doc_type.
    """
    return _post_file("/upload", uploaded_file, INGEST_TIMEOUT)


def start_analysis(document_id):
    """Start real risk and sentiment analysis for an ingested document."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/analyze/{int(document_id)}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)

        if getattr(exc, "response", None) is not None:
            detail = _error_detail(exc.response, detail)

        raise RuntimeError(f"Could not start analysis: {detail}") from exc
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid document ID.") from exc


def get_job(job_id):
    """Get the status and result of an analysis job."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/jobs/{int(job_id)}",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)

        if getattr(exc, "response", None) is not None:
            detail = _error_detail(exc.response, detail)

        raise RuntimeError(f"Could not retrieve analysis status: {detail}") from exc
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid analysis job ID.") from exc


def get_latest_analysis(document_id):
    """Retrieve the latest completed analysis without starting a new job."""
    try:
        response = requests.get(
            f"{API_BASE_URL}/documents/{int(document_id)}/analysis",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)

        if getattr(exc, "response", None) is not None:
            detail = _error_detail(exc.response, detail)

        raise RuntimeError(f"Could not retrieve completed analysis: {detail}") from exc
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Invalid document ID.") from exc


def get_analysis(company=None, quarter=None):
    """Load the existing mock analysis until the dashboard is migrated."""
    if not _MOCK_FILE.exists():
        raise RuntimeError(f"Mock analysis file not found: {_MOCK_FILE.name}")

    try:
        return json.loads(_MOCK_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not load mock analysis: {exc}") from exc


def ask_question(question, history=None):
    """Temporary mock chat response; real chat integration is separate."""
    data = get_analysis()

    return {
        "answer": (
            "This is a mock response. Real document-based chat "
            "has not yet been connected."
        ),
        "citations": data.get("citations", []),
    }
