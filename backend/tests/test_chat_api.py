import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import chat_api
from app.database import Base, get_db
from app.main import app
from app.models import ChatMessage, Company, Conversation, Document


@pytest.fixture
def chat_test_setup():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestingSessionLocal() as db:
        company = Company(name="Chat API Test Company")
        db.add(company)
        db.commit()
        db.refresh(company)

        document = Document(
            company_id=company.id,
            filename="test_transcript.txt",
            document_type="transcript",
            content=(
                "Revenue declined by 12 percent due to supply constraints."
            ),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        document_id = document.id

    try:
        with TestClient(app) as client:
            yield client, TestingSessionLocal, document_id
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_chat_success_saves_messages_and_citations(
    chat_test_setup, monkeypatch
):
    client, SessionLocal, document_id = chat_test_setup
    quote = "Revenue declined by 12 percent due to supply constraints."

    def fake_run_chat(message, history, text, doc_id):
        assert message == "Why did revenue decline?"
        assert "supply constraints" in text
        return None, {
            "result": {
                "answer": "Revenue declined because of supply constraints.",
                "citations": [{"doc_id": str(doc_id), "quote": quote}],
            },
            "issues": [],
        }

    monkeypatch.setattr(chat_api, "_run_chat", fake_run_chat)

    response = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "message": "Why did revenue decline?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Revenue declined because of supply constraints."
    assert data["answered"] is True
    assert data["citations"] == [
        {"doc_id": str(document_id), "quote": quote}
    ]
    assert data["conversation_id"] > 0
    assert data["message_id"] > 0

    with SessionLocal() as db:
        conversation = db.get(Conversation, data["conversation_id"])
        assert conversation is not None
        assert conversation.document_id == document_id

        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conversation.id)
            .order_by(ChatMessage.id)
            .all()
        )
        assert [message.role for message in messages] == [
            "user",
            "assistant",
        ]
        assert messages[0].content == "Why did revenue decline?"
        assert messages[1].content == data["answer"]
        assert quote in messages[1].citations_json


def test_chat_missing_document_returns_404(chat_test_setup):
    client, _, _ = chat_test_setup

    response = client.post(
        "/chat",
        json={
            "document_id": 999999,
            "message": "Summarize this document",
        },
    )

    assert response.status_code == 404


def test_chat_agent_failure_returns_502(chat_test_setup, monkeypatch):
    client, _, document_id = chat_test_setup

    def fake_run_chat(message, history, text, doc_id):
        raise RuntimeError("Simulated analyst failure")

    monkeypatch.setattr(chat_api, "_run_chat", fake_run_chat)

    response = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "message": "Summarize this document",
        },
    )

    assert response.status_code == 502


def test_chat_without_citations_is_unanswered(
    chat_test_setup, monkeypatch
):
    client, _, document_id = chat_test_setup

    def fake_run_chat(message, history, text, doc_id):
        return None, {
            "result": {
                "answer": "The document does not provide that information.",
                "citations": [],
            },
            "issues": ["No supporting passage found"],
        }

    monkeypatch.setattr(chat_api, "_run_chat", fake_run_chat)

    response = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "message": "What was the CEO's favorite color?",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answered"] is False
    assert data["citations"] == []
    assert data["issues"] == ["No supporting passage found"]


def test_get_conversation_returns_saved_messages(chat_test_setup, monkeypatch):
    client, _, document_id = chat_test_setup

    def fake_run_chat(message, history, text, doc_id):
        return None, {
            "result": {
                "answer": "Revenue declined due to supply constraints.",
                "citations": [
                    {
                        "doc_id": str(doc_id),
                        "quote": "supply constraints",
                    }
                ],
            },
            "issues": [],
        }

    monkeypatch.setattr(chat_api, "_run_chat", fake_run_chat)

    created = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "message": "Why did revenue decline?",
        },
    )
    assert created.status_code == 200
    conversation_id = created.json()["conversation_id"]

    response = client.get(f"/chat/{conversation_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conversation_id
    assert data["document_id"] == document_id
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert data["messages"][1]["citations"][0]["quote"] == "supply constraints"


def test_chat_followup_uses_existing_conversation(chat_test_setup, monkeypatch):
    client, _, document_id = chat_test_setup
    calls = []

    def fake_run_chat(message, history, text, doc_id):
        calls.append((message, history, text, doc_id))
        return None, {
            "result": {
                "answer": (
                    "Management expects continued revenue growth."
                    if history
                    else "Revenue declined due to supply constraints."
                ),
                "citations": [
                    {"doc_id": str(doc_id), "quote": "continued revenue growth"}
                ] if history else [
                    {"doc_id": str(doc_id), "quote": "supply constraints"}
                ],
            },
            "issues": [],
        }

    monkeypatch.setattr(chat_api, "_run_chat", fake_run_chat)

    first = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "message": "Why did revenue decline?",
        },
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = client.post(
        "/chat",
        json={
            "document_id": document_id,
            "conversation_id": conversation_id,
            "message": "What about the outlook?",
        },
    )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == conversation_id
    assert second.json()["answer"] == "Management expects continued revenue growth."
    assert len(calls) == 2
    assert calls[1][0] == "What about the outlook?"
    assert len(calls[1][1]) == 2
    assert calls[1][1][0] == (
        "user",
        "Why did revenue decline?",
    )
