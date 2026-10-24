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
4. support_ids: the IDs (like "S12") of the 1 to 3 sentences that directly support the answer. Do not copy text; give IDs only. Every number in your answer must be inside one of the cited sentences; if a figure and its label are in different sentences, cite both.
5. A line such as "Net income $59,688 $58,321 $26,422" is a table row: label first, then values for different periods. If you cannot tell which value belongs to the period asked, say so in the answer.
6. Answer only what was asked. Do not add growth rates, comparisons or other periods unless the question asks for them.
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
    s = re.sub(r"\b(?:Q[1-4]|H[12]|FY\s?\d{2,4})\b", " ", s, flags=re.I)   # labels like Q1 are not figures
    s = re.sub(r"(?<![$\d,.])(?:19|20)\d{2}(?![\d,]|\.\d|\s*(?:million|billion|%|percent))", " ", s)   # plain years are not figures
    return {n.replace(",", "").rstrip(".") for n in re.findall(r"\d[\d,]*\.?\d*", s)}

def _unsupported_numbers(answer, cited):
    have = set().union(*[_numbers(c) for c in cited]) if cited else set()
    return sorted(n for n in _numbers(answer) if n not in have)

def _has_contradictory_direction(answer, cited):
    """Reject clear directional contradictions in cited evidence."""
    opposites = [
        (
            {"increase", "increased", "increases", "increasing", "growth", "grew", "rise", "rose", "higher", "up"},
            {"decrease", "decreased", "decreases", "decreasing", "decline", "declined", "fell", "fall", "lower", "down"},
        ),
        (
            {"improve", "improved", "improves", "improving", "better"},
            {"worsen", "worsened", "worsens", "worsening", "deteriorate", "deteriorated", "worse"},
        ),
        (
            {"profit", "profitable", "profits"},
            {"loss", "losses", "unprofitable"},
        ),
        (
            {"stable", "unchanged", "flat"},
            {"volatile", "fluctuating", "unstable"},
        ),
    ]

    def words(text):
        return set(re.findall(r"[a-z]+", text.lower()))

    answer_words = words(answer)
    cited_words = (
        set().union(*(words(quote) for quote in cited))
        if cited
        else set()
    )

    for left, right in opposites:
        answer_left = bool(answer_words & left)
        answer_right = bool(answer_words & right)
        cited_left = bool(cited_words & left)
        cited_right = bool(cited_words & right)

        # Do not reject an answer if the evidence also contains
        # the answer's direction for a different metric.
        if answer_left and cited_right and not cited_left:
            return True
        if answer_right and cited_left and not cited_right:
            return True

    return False

def _has_lexical_support(answer, cited):
    """Reject clearly unrelated citations using meaningful word overlap.

    This is a conservative lexical safeguard, not a semantic entailment model.
    """
    stop_words = {
        "the", "and", "for", "that", "with", "from", "this", "was",
        "were", "are", "is", "by", "to", "of", "in", "on", "at",
        "a", "an", "as", "it", "its", "be", "because", "due",
        "what", "why", "when", "how", "did", "does", "do",
        "has", "have", "had", "can", "could", "would", "should",
        "will", "about", "into", "than", "then", "their", "they",
        "them", "our", "we", "you", "your",
    }

    def meaningful_words(text):
        return {
            word
            for word in re.findall(r"[a-z]{3,}", text.lower())
            if word not in stop_words
        }

    answer_words = meaningful_words(answer)
    citation_words = (
        set().union(*(meaningful_words(quote) for quote in cited))
        if cited
        else set()
    )

    if not answer_words:
        return True

    # Require more than one shared meaningful word when the answer has
    # multiple meaningful words. This rejects incidental single-word matches.
    overlap = answer_words & citation_words
    if len(answer_words) >= 2:
        return len(overlap) >= 2

    return bool(overlap)

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
    system = SYSTEM.replace("{schema}", json.dumps(ModelOut.model_json_schema()))
    out, retries = ask_json(system, user, ModelOut)
    if not out.answerable:            # abstain only if two attempts agree (the model sometimes fails once)
        out2, _ = ask_json(system, user, ModelOut)
        if out2.answerable:
            out = out2
    if len(out.support_ids) > 5:      # model ignored rule 4 (once returned ~130 ids): one stricter retry
        out, retries = ask_json(system, user + "\n\nREMINDER: support_ids must contain at most 3 IDs.", ModelOut)

    issues, cites = [], []
    for sid in out.support_ids[:3]:
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
    elif _has_contradictory_direction(out.answer, cites):
        issues.append("answer contradicts the direction stated in its citation")
        answer, cites = NOT_FOUND, []
    elif not _has_lexical_support(out.answer, cites):
        issues.append("citation text does not lexically support the answer")
        answer, cites = NOT_FOUND, []
    else:
        bad = _unsupported_numbers(out.answer, cites)
        if bad:        # citation repair: the model sometimes cites the label line, not the value line
            aw = {w for w in re.findall(r"[a-z]{3,}", out.answer.lower())}
            for u in units:
                if len(cites) >= 3:
                    break
                if u not in cites and _norm(u) in src and any(n in _numbers(u) for n in bad) \
                        and len(aw & set(re.findall(r"[a-z]{3,}", u.lower()))) >= 2:
                    cites.append(u)
            bad = _unsupported_numbers(out.answer, cites)
        if bad:
            issues.append("numbers in the answer not found in its citations: " + ", ".join(bad))
            answer, cites = NOT_FOUND, []
    result = AnalystAnswer(answer=answer, citations=[Citation(doc_id=doc_id, quote=c) for c in cites])
    return {"result": result.model_dump(), "issues": issues, "retries": retries,
            "retrieved": [{"chunk_id": h["chunk_id"], "score": round(h["score"], 3)} for h in hits]}

from .normalize import normalize_pdf_text as _normalize_pdf_text
_answer_question_raw = answer_question

def answer_question(question, text, doc_id="doc", k=5):
    return _answer_question_raw(question, _normalize_pdf_text(text), doc_id=doc_id, k=k)
