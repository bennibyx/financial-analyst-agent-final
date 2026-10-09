
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.main import app
from app.database import get_db
from app.models import Document

client = TestClient(app)


class FakeDB:
    def __init__(self, document):
        self.document = document

    def get(self, model, document_id):
        return self.document if document_id == 123 else None


def fake_document():
    return SimpleNamespace(
        id=123,
        company_id=1,
        filename="sample.txt",
        content="The company's revenue was $100 million.",
    )


def make_agent_module(answer_question):
    return SimpleNamespace(answer_question=answer_question)


def run_fake_agent(*args, **kwargs):
    return {
        "result": {
            "answer": "Revenue was $100 million.",
            "citations": [
                {
                    "doc_id": "123",
                    "quote": "The company's revenue was $100 million.",
                }
            ],
        }
    }


def failing_agent(*args, **kwargs):
    raise RuntimeError("Agent unavailable")


def timeout_agent(*args, **kwargs):
    raise asyncio.TimeoutError()


def missing_module(*args, **kwargs):
    raise ImportError("Agent dependencies unavailable")


def test_ask_returns_agent_answer_and_citations():
    document = fake_document()

    def get_test_db():
        yield FakeDB(document)

    app.dependency_overrides[get_db] = get_test_db
    try:
        with patch.dict(
            sys.modules,
            {"agents.analyst": make_agent_module(run_fake_agent)},
        ):
            response = client.post(
                "/ask",
                json={
                    "question": "What was the revenue?",
                    "document_id": "123",
                },
            )

        assert response.status_code == 200
        assert response.json()["answer"] == "Revenue was $100 million."
        assert response.json()["citations"][0]["doc_id"] == "123"
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ask_returns_fallback_when_agent_fails():
    document = fake_document()

    def get_test_db():
        yield FakeDB(document)

    app.dependency_overrides[get_db] = get_test_db
    try:
        with patch.dict(
            sys.modules,
            {"agents.analyst": make_agent_module(failing_agent)},
        ):
            response = client.post(
                "/ask",
                json={
                    "question": "What was the revenue?",
                    "document_id": "123",
                },
            )

        assert response.status_code == 200
        assert "sample response" in response.json()["answer"].lower()
        assert response.json()["citations"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ask_rejects_missing_question():
    response = client.post("/ask", json={"document_id": "123"})
    assert response.status_code == 422


def test_ask_returns_404_for_unknown_document():
    def get_test_db():
        yield FakeDB(None)

    app.dependency_overrides[get_db] = get_test_db
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What was the revenue?",
                "document_id": "999",
            },
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ask_rejects_non_numeric_document_id():
    def get_test_db():
        yield FakeDB(fake_document())

    app.dependency_overrides[get_db] = get_test_db
    try:
        response = client.post(
            "/ask",
            json={
                "question": "What was the revenue?",
                "document_id": "invalid",
            },
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_ask_returns_fallback_when_agent_import_fails():
    document = fake_document()

    def get_test_db():
        yield FakeDB(document)

    app.dependency_overrides[get_db] = get_test_db
    try:
        with patch.dict(sys.modules, {"agents.analyst": None}):
            response = client.post(
                "/ask",
                json={
                    "question": "What was the revenue?",
                    "document_id": "123",
                },
            )

        assert response.status_code == 200
        assert "sample response" in response.json()["answer"].lower()
        assert response.json()["citations"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)