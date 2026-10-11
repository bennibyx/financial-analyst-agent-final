"""POST /chat (conversation history + citations passthrough) and GET /chat/{conversation_id}."""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api_contract import ApiError, ErrorResponse
from app.database import Base, engine, get_db
from app.models import ChatMessage, Conversation, Document

logger = logging.getLogger(__name__)
router = APIRouter()

# The server runs from backend/, but the agents live in the project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

CHAT_TIMEOUT_S = 150.0   # the first question on a document also builds a search index
HISTORY_MESSAGES = 6     # how many earlier messages are used to resolve follow-ups

# Creates any missing tables (conversations, chat_messages); never alters existing ones.
Base.metadata.create_all(bind=engine)


# ---------- Request / response models ----------

class ChatRequest(BaseModel):
    document_id: int = Field(..., examples=[2])
    message: str = Field(..., min_length=1, max_length=2000,
                         examples=["What did management say about supply constraints?"])
    conversation_id: Optional[int] = Field(
        None, description="Omit to start a new conversation; send it back to continue one."
    )


class CitationOut(BaseModel):
    doc_id: str
    quote: str


class ChatResponse(BaseModel):
    conversation_id: int
    document_id: int
    message_id: int = Field(..., description="Id of the assistant message that was saved.")
    answer: str
    citations: list[CitationOut]
    answered: bool = Field(
        ..., description="False when the document does not contain the answer (no citations)."
    )
    rewritten_question: Optional[str] = Field(
        None, description="For follow-ups: the standalone question actually searched. Null if unchanged."
    )
    issues: list[str] = Field([], description="Verification notes from the analyst agent.")


class MessageOut(BaseModel):
    message_id: int
    role: str = Field(..., examples=["user"])
    content: str
    citations: list[CitationOut] = []
    created_at: datetime


class ConversationOut(BaseModel):
    conversation_id: int
    document_id: int
    created_at: datetime
    messages: list[MessageOut]


# ---------- Follow-up rewriting ----------

class _Rewrite(BaseModel):
    question: str


REWRITE_SYSTEM = """You rewrite the user's latest message as ONE standalone question that makes sense without the conversation. Return ONLY JSON matching this schema:
{schema}

RULES:
1. Use ONLY the conversation to resolve references such as "it", "that", "the next quarter", "they". Add no new facts.
2. Do not answer the question.
3. If the latest message is already a standalone question, return it unchanged.
4. Keep it short: one question.
"""


def _rewrite(message: str, history: list[tuple[str, str]]) -> str:
    from agents.llm import ask_json

    convo = "\n".join(f"{role.upper()}: {content[:500]}" for role, content in history)
    system = REWRITE_SYSTEM.replace("{schema}", json.dumps(_Rewrite.model_json_schema()))
    user = f"CONVERSATION SO FAR:\n{convo}\n\nLATEST USER MESSAGE: {message}"
    out, _ = ask_json(system, user, _Rewrite, max_tokens=300)
    question = (out.question or "").strip()
    return question or message


def _run_chat(message: str, history: list[tuple[str, str]], text: str, doc_id: str):
    """Runs in a worker thread: (optional) rewrite, then the analyst agent."""
    from agents.analyst import answer_question

    question, rewritten = message, None
    if history:
        try:
            candidate = _rewrite(message, history)
            if candidate != message:
                question, rewritten = candidate, candidate
        except Exception:
            logger.exception("Question rewrite failed; using the original question")
    out = answer_question(question, text, doc_id=doc_id)
    return rewritten, out


def _citations_of(msg: ChatMessage) -> list[CitationOut]:
    if not msg.citations_json:
        return []
    try:
        return [CitationOut.model_validate(c) for c in json.loads(msg.citations_json)]
    except Exception:
        logger.exception("Could not read citations of message %s", msg.id)
        return []


# ---------- Endpoints ----------

@router.post(
    "/chat",
    response_model=ChatResponse,
    tags=["chat"],
    summary="Ask a question about a document, with conversation history",
    description="Omit conversation_id to start a new conversation; send the returned conversation_id "
    "with later messages so follow-up questions work. The first question on a document can take "
    "30-60 seconds (a search index is built once); later ones are faster. Citations are exact "
    "quotes from the document.",
    responses={
        404: {"model": ErrorResponse, "description": "document_not_found / conversation_not_found"},
        422: {"model": ErrorResponse, "description": "empty_message / no_text_content / conversation_document_mismatch"},
        502: {"model": ErrorResponse, "description": "chat_failed"},
        504: {"model": ErrorResponse, "description": "chat_timeout"},
    },
)
async def chat(req: ChatRequest, db: Session = Depends(get_db)):
    message = req.message.strip()
    if not message:
        raise ApiError(422, "empty_message", "The message is empty.")

    doc = db.get(Document, req.document_id)
    if doc is None:
        raise ApiError(404, "document_not_found", "Document not found.")
    if not doc.content or not doc.content.strip():
        raise ApiError(422, "no_text_content", "This document has no text to answer from.")

    conv: Optional[Conversation] = None
    history: list[tuple[str, str]] = []
    if req.conversation_id is not None:
        conv = db.get(Conversation, req.conversation_id)
        if conv is None:
            raise ApiError(404, "conversation_not_found", "Conversation not found.")
        if conv.document_id != doc.id:
            raise ApiError(422, "conversation_document_mismatch",
                           "This conversation belongs to a different document.")
        rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conv.id)
            .order_by(ChatMessage.id.desc())
            .limit(HISTORY_MESSAGES)
        ).all()
        history = [(m.role, m.content) for m in reversed(rows)]

    try:
        import agents.analyst  # noqa: F401  (availability check)
    except Exception:
        logger.exception("Could not import the analyst agent")
        raise ApiError(500, "agent_unavailable", "The analyst agent could not be loaded.")

    try:
        rewritten, out = await asyncio.wait_for(
            asyncio.to_thread(_run_chat, message, history, doc.content, str(doc.id)),
            timeout=CHAT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning("Chat timed out for document %s", doc.id)
        raise ApiError(504, "chat_timeout", "The answer took too long. Please try again.")
    except Exception:
        logger.exception("Chat failed for document %s", doc.id)
        raise ApiError(502, "chat_failed", "The analyst agent failed on this question.")

    result = out.get("result", {})
    answer = result.get("answer", "")
    citations = result.get("citations", [])

    try:
        if conv is None:
            conv = Conversation(document_id=doc.id)
            db.add(conv)
            db.flush()
        db.add(ChatMessage(conversation_id=conv.id, role="user", content=message))
        assistant = ChatMessage(
            conversation_id=conv.id, role="assistant", content=answer,
            citations_json=json.dumps(citations),
        )
        db.add(assistant)
        db.commit()
        db.refresh(assistant)
    except Exception:
        db.rollback()
        logger.exception("Could not save the chat messages")
        raise ApiError(500, "chat_save_failed", "The answer was found but could not be saved.")

    return ChatResponse(
        conversation_id=conv.id,
        document_id=doc.id,
        message_id=assistant.id,
        answer=answer,
        citations=[CitationOut.model_validate(c) for c in citations],
        answered=bool(citations),
        rewritten_question=rewritten,
        issues=[str(i) for i in out.get("issues", [])],
    )


@router.get(
    "/chat/{conversation_id}",
    response_model=ConversationOut,
    tags=["chat"],
    summary="Get a whole conversation (to reload a chat page)",
    responses={404: {"model": ErrorResponse, "description": "conversation_not_found"}},
)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise ApiError(404, "conversation_not_found", "Conversation not found.")
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id)
        .order_by(ChatMessage.id)
    ).all()
    return ConversationOut(
        conversation_id=conv.id,
        document_id=conv.document_id,
        created_at=conv.created_at,
        messages=[
            MessageOut(message_id=m.id, role=m.role, content=m.content,
                       citations=_citations_of(m), created_at=m.created_at)
            for m in rows
        ],
    )
