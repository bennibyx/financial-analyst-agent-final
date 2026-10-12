"""agents/service.py - the ONLY door the backend uses to reach the agents.
Every function returns an Envelope and never raises."""
import hashlib
import time
from typing import Callable, Optional
from pydantic import BaseModel

CONTRACT_VERSION = "1.0"

class ErrorInfo(BaseModel):
    code: str      # BAD_INPUT | TIMEOUT | INTERNAL
    message: str

class Meta(BaseModel):
    agent: str
    latency_ms: int
    doc_id: Optional[str] = None
    contract_version: str = CONTRACT_VERSION
    used_fallback: bool = False
    fallback_reason: Optional[str] = None

class Envelope(BaseModel):
    ok: bool
    data: Optional[dict] = None
    error: Optional[ErrorInfo] = None
    meta: Meta

def _doc_id(text: str, doc_id: Optional[str]) -> str:
    # Same text -> same id (index cache hit); different text -> different id (no stale index).
    return doc_id or "d_" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]

def _run(agent: str, call: Callable[[], object], text: str, doc_id: str) -> Envelope:
    t0 = time.time()
    def meta(**extra):
        return Meta(agent=agent, doc_id=doc_id,
                    latency_ms=max(1, int((time.time() - t0) * 1000)), **extra)
    if not isinstance(text, str) or len(text.strip()) < 50:   # validate BEFORE spending tokens
        return Envelope(ok=False, meta=meta(),
                        error=ErrorInfo(code="BAD_INPUT", message="text is empty or too short"))
    try:
        result = call()
        if hasattr(result, "model_dump"):        # Pydantic object -> dict
            result = result.model_dump()
        if not isinstance(result, dict):
            result = {"result": result}
        return Envelope(ok=True, data=result,
                        meta=meta(used_fallback=bool(result.get("used_fallback", False)),
                                  fallback_reason=result.get("fallback_reason")))
    except TimeoutError as e:
        return Envelope(ok=False, meta=meta(), error=ErrorInfo(code="TIMEOUT", message=str(e)))
    except Exception as e:                        # a crash must never reach the API
        return Envelope(ok=False, meta=meta(),
                        error=ErrorInfo(code="INTERNAL", message=f"{type(e).__name__}: {e}"))

# ---- the 4 public functions the backend calls (real agents, lazy imports) ----
def extract_document(text: str, doc_type: str = "auto", doc_id: Optional[str] = None) -> Envelope:
    did = _doc_id(text, doc_id)
    def call():
        from agents.extraction_agent import run_extraction
        return run_extraction(text, doc_type=doc_type, doc_id=did)
    return _run("extraction", call, text, did)

def analyze_document(text: str, doc_id: Optional[str] = None) -> Envelope:
    did = _doc_id(text, doc_id)
    def call():
        from agents.risk_sentiment import analyze_risk_sentiment
        return analyze_risk_sentiment(text)
    return _run("risk_sentiment", call, text, did)

def ask_document(question: str, text: str, doc_id: Optional[str] = None) -> Envelope:
    did = _doc_id(text, doc_id)
    if not isinstance(question, str) or not question.strip():
        return Envelope(ok=False, meta=Meta(agent="analyst", latency_ms=1, doc_id=did),
                        error=ErrorInfo(code="BAD_INPUT", message="question is empty"))
    def call():
        from agents.analyst import answer_question
        return answer_question(question, text, doc_id=did)
    return _run("analyst", call, text, did)

def run_pipeline(text: str, question: Optional[str] = None, doc_id: Optional[str] = None) -> Envelope:
    did = _doc_id(text, doc_id)
    def call():
        from agents.orchestrator import orchestrate
        return orchestrate(text, question=question, doc_id=did)
    return _run("orchestrator", call, text, did)
