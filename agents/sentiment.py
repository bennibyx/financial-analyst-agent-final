# agents/sentiment.py -- Sentiment & Tone Agent v1 (earnings-call transcripts)
import json, re
from typing import Literal, Optional
from pydantic import BaseModel, Field
from .llm import ask_json
from .verify import clean_text

class Evidence(BaseModel):
    quote: str            # exact words from the transcript
    note: str             # one short sentence: why it matters

class Pushback(BaseModel):
    topic: str
    analyst_quote: str
    management_quote: str  # "" if not found
    evasive: bool          # True only if management did not answer the specific question

class SentimentResult(BaseModel):
    overall_tone: Literal["positive", "neutral", "negative"]
    tone_score: float = Field(ge=-1, le=1)                          # -1 very negative ... +1 very positive
    prepared_remarks_score: Optional[float] = Field(default=None, ge=-1, le=1)
    qa_score: Optional[float] = Field(default=None, ge=-1, le=1)   # null if no Q&A in the text
    hedging_level: Literal["low", "medium", "high"]
    hedging_examples: list[Evidence]
    positive_signals: list[Evidence]
    negative_signals: list[Evidence]
    analyst_pushback: list[Pushback]

SYSTEM = """You analyze the tone of an earnings-call transcript. Return ONLY JSON matching this schema:
{schema}

RULES:
1. Use ONLY the transcript. No outside knowledge, no guessing about the stock or the market.
2. Every quote must be copied EXACTLY, word for word, from the transcript (max 40 words). Never paraphrase inside a quote. Never add square brackets, ellipses or your own words inside a quote; if you need to shorten it, copy a shorter contiguous piece of the text.
3. tone_score judges management's wording and confidence, NOT whether the results were good. -1 very negative, 0 neutral, +1 very positive.
4. prepared_remarks_score covers the scripted opening remarks. qa_score covers management's answers to analysts. Use null if there is no Q&A.
5. Hedging = wording that softens a commitment ("we expect", "subject to", "difficult to predict", "assuming", "depends on"). List up to 5 of the clearest examples. hedging_level is "high" only if most guidance statements are hedged.
6. analyst_pushback = analyst questions that challenge, doubt, or press a concern (a follow-up pressing the same issue counts). Up to 5. evasive=true only if management's reply does not answer the specific question asked. If the text contains NO analyst questions (for example a prepared CFO commentary), analyst_pushback MUST be an empty list.
7. positive_signals and negative_signals: up to 4 each, about what management said. Only management's own statements count; an analyst's question is never a signal.
8. If nothing fits a list, return an empty list. Never invent items to fill a list.
"""

def _norm(s):
    s = s.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", s).strip().lower()

def verify_quotes(r, text):
    """Drop every quote that is not found word-for-word in the source. Returns (result, issues, kept, total)."""
    src, issues, kept, total = _norm(text), [], 0, 0
    ok = lambda q: bool(q) and _norm(q) in src
    for field in ("hedging_examples", "positive_signals", "negative_signals"):
        good = []
        for e in getattr(r, field):
            total += 1
            if ok(e.quote):
                good.append(e); kept += 1
            else:
                issues.append(f"{field}: quote not found, dropped: " + e.quote[:80])
        setattr(r, field, good)
    good = []
    for p in r.analyst_pushback:
        total += 1
        if ok(p.analyst_quote):
            kept += 1
            if p.management_quote and not ok(p.management_quote):
                issues.append("analyst_pushback: management quote not found, cleared")
                p.management_quote = ""
            good.append(p)
        else:
            issues.append("analyst_pushback: analyst quote not found, dropped: " + p.analyst_quote[:80])
    r.analyst_pushback = good
    return r, issues, kept, total

def analyze_sentiment(text):
    text = clean_text(text)
    schema = json.dumps(SentimentResult.model_json_schema())
    result, retries = ask_json(SYSTEM.replace("{schema}", schema), "TRANSCRIPT:\n" + text, SentimentResult)
    result, issues, kept, total = verify_quotes(result, text)
    return {"result": result.model_dump(), "issues": issues, "retries": retries,
            "quotes_kept": kept, "quotes_total": total}
