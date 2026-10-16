
"""Frontend API client: real document uploads, with mock analysis preserved."""
import json
import os
from pathlib import Path

import requests

API_BASE_URL = os.getenv(
    "FINANCIAL_ANALYST_API_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

_MOCK_FILE = Path(__file__).parent / "mock_analysis.json"
USE_MOCK = True


def upload_document(uploaded_file):
    """Upload a Streamlit file to the FastAPI backend."""
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    try:
        response = requests.post(
            f"{API_BASE_URL}/upload-raw",
            files=files,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        detail = str(exc)
        if getattr(exc, "response", None) is not None:
            try:
                detail = exc.response.json().get("detail", detail)
            except ValueError:
                pass
        raise RuntimeError(f"Document upload failed: {detail}") from exc


def get_analysis(company=None, quarter=None):
    """Return analysis JSON while the real analysis integration is pending."""
    if USE_MOCK:
        return json.loads(_MOCK_FILE.read_text(encoding="utf-8"))
    raise NotImplementedError("Real analysis integration is pending.")


def ask_question(question, history):
    """Return a mock answer until the real chat API is integrated."""
    if USE_MOCK:
        data = get_analysis()
        return {
            "answer": "Mock answer: gross margin rose because of a better product mix [1][2].",
            "citations": data["citations"],
        }
    raise NotImplementedError("Real chat integration is pending.")
