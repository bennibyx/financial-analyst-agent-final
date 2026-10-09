# agents/risk_judge.py -- second pass: does each quote really support its risk title?
import json
from pydantic import BaseModel
from .llm import ask_json

class Verdict(BaseModel):
    index: int
    supports: bool   # the quote itself says what the title claims
    harm: bool       # the quote describes a problem, limit, cost or threat (not good news, not a neutral fact)

class Verdicts(BaseModel):
    verdicts: list[Verdict]

JUDGE = """You check risks extracted from an earnings call. For each numbered item, use ONLY the quote shown.
supports = true only if the quote itself says what the title claims.
harm = true only if the quote describes a problem, limit, cost or threat to the business. Good news, confidence statements, plans on track, and neutral facts are harm=false.
Return ONLY JSON matching this schema, with one verdict per item:
{schema}"""

def judge_support(r):
    if not r.risks:
        return r, []
    items = "\n".join(f"{i}. TITLE: {x.title} | QUOTE: {x.quote}" for i, x in enumerate(r.risks))
    v, _ = ask_json(JUDGE.replace("{schema}", json.dumps(Verdicts.model_json_schema())), items, Verdicts)
    ok = {d.index for d in v.verdicts if d.supports and d.harm}
    issues = [f"judge rejected: {x.title} | QUOTE: {x.quote[:160]}" for i, x in enumerate(r.risks) if i not in ok]
    r.risks = [x for i, x in enumerate(r.risks) if i in ok]
    return r, issues
