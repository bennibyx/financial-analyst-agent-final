# agents/risk.py -- Risk Agent v1 (earnings-call transcripts): headwinds and risk factors with severity
import json
from typing import Literal
from pydantic import BaseModel, Field
from .llm import ask_json
from .verify import clean_text
from .sentiment import _norm

class RiskItem(BaseModel):
    category: Literal["supply_chain", "demand", "competition", "regulatory_export",
                      "margin_cost", "macro", "execution", "other"]
    title: str                                  # max 8 words
    severity: int = Field(ge=1, le=5)
    status: Literal["current", "potential"]     # current = already hurting results; potential = may happen
    quantified: bool                            # True only if the quote contains a number for the impact
    quote: str                                  # exact words from the transcript
    explanation: str                            # one sentence, only from the transcript

class RiskResult(BaseModel):
    overall_risk_level: Literal["low", "medium", "high"]
    risks: list[RiskItem]

SYSTEM = """You extract risks and headwinds from an earnings-call transcript. Return ONLY JSON matching this schema:
{schema}

RULES:
1. Use ONLY the transcript. No outside knowledge about the company or the market.
2. Every quote must be copied EXACTLY, word for word, from the transcript (max 40 words). Never add brackets, ellipses or your own words inside a quote.
3. A risk is something management or an analyst says could hurt, or already hurts, the business (supply limits, export restrictions, customer concentration, rising costs, competition, weak demand in a segment).
4. Do not list good news as a risk (for example growing market share, rising revenue, a new reporting format). The quote must itself describe the harm named in the title; if the quote does not say it, do not list it. Use a different quote for each risk and never reuse a quote.
5. severity (judge by how the transcript describes the impact):
   1 = mentioned in passing, no impact stated.
   2 = a possible issue, impact not quantified.
   3 = a clear issue with a limited or qualitative impact.
   4 = a quantified impact, or one management says affects guidance.
   5 = a major quantified impact, such as lost revenue or a large guidance cut.
6. status="current" only if the transcript says the issue already affects results; otherwise "potential".
7. quantified=true only if the quote contains a number that measures the harm itself (lost revenue, a cost increase, a guidance cut). A number about something else, such as total supply commitments, does not count. When unsure, quantified=false.
8. List at most 5 risks, most severe first. Fewer is better and an empty list is fine. Never pad the list. If the transcript contains no risks, return an empty list. Never invent risks to fill the list.
9. overall_risk_level: "high" only if there are 2 or more risks with severity 4 or higher.
"""

def verify_risks(r, text):
    """Drop any risk whose quote is not found word-for-word in the source."""
    src, kept, issues = _norm(text), [], []
    for x in r.risks:
        if x.quote and _norm(x.quote) in src:
            kept.append(x)
        else:
            issues.append("risk quote not found, dropped: " + x.quote[:80])
    total = len(r.risks)
    import re
    seen, final = set(), []
    for x in sorted(kept, key=lambda x: -x.severity):
        key = _norm(x.quote)
        if key in seen:
            issues.append('duplicate quote, dropped: ' + x.title)
            continue
        seen.add(key)
        x.quantified = bool(re.search(r'[$%]|\b(billion|million|percent)\b', x.quote))   # computed in code, not trusted from the model
        if x.severity == 5 and not x.quantified:
            x.severity = 4
            issues.append('severity 5 without a number in the quote, set to 4: ' + x.title)
        final.append(x)
    r.risks = final
    n_high = sum(1 for x in final if x.severity >= 4)
    r.overall_risk_level = 'high' if n_high >= 2 else ('medium' if (n_high == 1 or any(x.severity == 3 for x in final)) else 'low')
    return r, issues, len(kept), total

def analyze_risk(text):
    text = clean_text(text)
    schema = json.dumps(RiskResult.model_json_schema())
    result, retries = ask_json(SYSTEM.replace("{schema}", schema), "TRANSCRIPT:\n" + text, RiskResult)
    result, issues, kept, total = verify_risks(result, text)
    from .risk_judge import judge_support
    result, judge_issues = judge_support(result)
    issues += judge_issues
    n_high = sum(1 for x in result.risks if x.severity >= 4)
    result.overall_risk_level = 'high' if n_high >= 2 else ('medium' if (n_high == 1 or any(x.severity == 3 for x in result.risks)) else 'low')
    return {"result": result.model_dump(), "issues": issues, "retries": retries,
            "quotes_kept": kept, "quotes_total": total}
