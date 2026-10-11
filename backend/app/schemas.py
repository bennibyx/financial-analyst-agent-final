
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str = Field(min_length=1)


class CitationResponse(BaseModel):
    doc_id: str
    quote: str


class AnalystAnswerResponse(BaseModel):
    used_fallback: bool = False            # True = the agent did NOT answer; this is the canned text
    fallback_reason: str | None = None     # why: timeout, import error, empty answer...
    answer: str
    citations: list[CitationResponse]
