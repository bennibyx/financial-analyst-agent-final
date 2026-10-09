# agents/analyst.py -- Interactive Analyst (Q&A) Agent v2: retrieve -> number the sentences -> model picks IDs -> verify
import json, re
from pydantic import BaseModel
from .llm import ask_json
from .retrieval import build_index, search
from .schemas import AnalystAnswer, Citation
from .sentiment import _norm
from .verify import clean_text

NOT_FOUND = "The document does not say."

class ModelOut(BaseModel):          # internal; the public output is AnalystAnswer from schemas.py
    answerable: bool
    answer: str
    support_ids: list[str]

SYSTEM = """You answer a question about an earnings-call transcript using ONLY the numbered sentences given. Return ONLY JSON matching this schema:
{schema}

RULES:
1. Use ONLY the numbered sentences. No outside knowledge, no guessing, no estimating.
2. If they do not contain the answer, set answerable=false, answer="", support_ids=[].
3. answer: at most 3 sentences. Every number in the answer must appear in a sentence you cite. Copy numbers exactly as stated.
4. support_ids: the IDs (like "S12") of the 1 to 3 sentences that directly support the answer. Do not copy text; give IDs only.
5. A line such as "Net income $59,688 $58,321 $26,422" is a table row: label first, then values for different periods. If you cannot tell which value belongs to the period asked, say so in the answer.
"""

def make_units(chunk_text):
    """Prose lines become sentences; short label lines are joined with the short lines after them (table rows)."""
    lines = [l.strip() for l in chunk_text.splitlines()]
    merged = []                       # a PDF line break inside a sentence must not split it
    for l in lines:
        if merged and l and merged[-1] and len(l.split()) >= 4 and len(merged[-1].split()) >= 4 \
                and not re.search(r"[.!?:]$", merged[-1]):
            merged[-1] += " " + l
        else:
            merged.append(l)
    lines = merged
    units = []
    for i, line in enumerate(lines):
        if not line:
            continue
        if len(line.split()) >= 8:
            units += [s.strip() for s in re.split(r"(?<=[.!?])\s+", line) if s.strip()]
        elif re.search(r"[A-Za-z]{3}", line):                     # a label, not a bare number
            window = [line]
            for nxt in lines[i + 1:i + 4]:
                if not nxt or len(nxt.split()) >= 8:
                    break
                window.append(nxt)
            units.append(" ".join(window))
    return units

def _numbers(s):
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", s)}

def _unsupported_numbers(answer, cited):
    have = set().union(*[_numbers(c) for c in cited]) if cited else set()
    return sorted(n for n in _numbers(answer) if n not in have)

def answer_question(question, text, doc_id="doc", k=5):
    vectors, meta = build_index(text, doc_id)
    hits = search(question, vectors, meta, k=k)
    units, seen = [], set()
    for h in hits:
        for u in make_units(h["text"]):
            if u not in seen:
                seen.add(u); units.append(u)
    context = "\n".join(f"[S{i + 1}] {u}" for i, u in enumerate(units))
    user = f"QUESTION: {question}\n\nNUMBERED SENTENCES:\n{context}"
    out, retries = ask_json(SYSTEM.replace("{schema}", json.dumps(ModelOut.model_json_schema())), user, ModelOut)

    issues, cites = [], []
    for sid in out.support_ids:
        m = re.fullmatch(r"S?(\d+)", sid.strip())
        if m and 1 <= int(m.group(1)) <= len(units):
            u = units[int(m.group(1)) - 1]
            if u not in cites:
                cites.append(u)
        else:
            issues.append("unknown support id ignored: " + sid)
    src = _norm(clean_text(text))
    cites = [c for c in cites if _norm(c) in src]                 # safety net; should always pass

    answer = out.answer
    if not out.answerable:
        answer, cites = NOT_FOUND, []
    elif not cites:
        answer = NOT_FOUND
        issues.append("no valid citation; answer replaced with not-found")
    else:
        bad = _unsupported_numbers(out.answer, cites)
        if bad:
            issues.append("numbers in the answer not found in its citations: " + ", ".join(bad))
            answer, cites = NOT_FOUND, []
    result = AnalystAnswer(answer=answer, citations=[Citation(doc_id=doc_id, quote=c) for c in cites])
    return {"result": result.model_dump(), "issues": issues, "retries": retries,
            "retrieved": [{"chunk_id": h["chunk_id"], "score": round(h["score"], 3)} for h in hits]}
