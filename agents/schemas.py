from typing import Literal, Optional
from pydantic import BaseModel, Field

Unit = Literal["USD_million", "USD_billion", "USD", "percent", "other"]

class Metric(BaseModel):
    name: Literal["revenue", "eps", "gross_margin", "operating_margin",
                  "net_income", "free_cash_flow"]
    value: Optional[float] = None
    unit: Unit
    period: str
    yoy_change_pct: Optional[float] = None
    qoq_change_pct: Optional[float] = None
    source_quote: str

class GuidanceItem(BaseModel):
    metric: str
    period: str
    low: Optional[float] = None
    high: Optional[float] = None
    unit: Unit
    qualitative: Optional[str] = None
    source_quote: str

class Risk(BaseModel):
    category: Literal["supply_chain", "macro", "regulatory", "competition",
                      "demand", "margin_pressure", "other"]
    description: str
    severity: int = Field(ge=1, le=5)
    source_quote: str

class Sentiment(BaseModel):
    overall: Literal["positive", "neutral", "negative"]
    score: float = Field(ge=-1, le=1)
    hedging_level: Literal["low", "medium", "high"]
    qa_pushback: Literal["none", "mild", "strong"]
    evidence_quotes: list[str]

class ExtractionResult(BaseModel):
    company: str
    period: str
    metrics: list[Metric]
    guidance: list[GuidanceItem] = []

class RiskSentimentResult(BaseModel):
    risks: list[Risk]
    sentiment: Sentiment

class Citation(BaseModel):
    doc_id: str
    quote: str

class AnalystAnswer(BaseModel):
    answer: str
    citations: list[Citation]
