
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    document_id: str = Field(min_length=1)


class CitationResponse(BaseModel):
    doc_id: str
    quote: str


class AnalystAnswerResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
