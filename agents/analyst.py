
"""Interactive Analyst: retrieve evidence, answer questions, and validate citations."""

import json
import re

from pydantic import BaseModel

from .llm import ask_json
from .retrieval import build_index, search
from .schemas import AnalystAnswer, Citation
from .sentiment import _norm
from .verify import clean_text

NOT_FOUND = "The document does not say."


class ModelOut(BaseModel):
    answerable: bool
    answer: str
    support_ids: list[str]


SYSTEM = """You answer a question about an earnings-call transcript using ONLY
the numbered sentences given. Return ONLY JSON matching this schema:
{schema}

RULES:
1. Use ONLY the numbered sentences. No outside knowledge, guessing, or estimating.
2. If they do not contain the answer, set answerable=false, answer="", support_ids=[].
3. Answer in at most 3 sentences. Every number in the answer must appear in a
   sentence you cite. Copy numbers exactly as stated.
4. support_ids must identify 1 to 3 sentences that directly support the answer.
   Give IDs only, such as "S12". If a figure and its label are in different
   sentences, cite both.
5. A line such as "Net income $59,688 $58,321 $26,422" is a table row:
   label first, then values for different periods. If the requested period
   cannot be identified, say so.
6. Answer only what was asked. Do not add growth rates, comparisons, or other
   periods unless requested.
"""


def make_units(chunk_text):
    """Convert prose into evidence sentences and preserve short table rows."""
    lines = [line.strip() for line in chunk_text.splitlines()]
    merged = []

    for line in lines:
        if (
            merged
            and line
            and merged[-1]
            and len(line.split()) >= 4
            and len(merged[-1].split()) >= 4
            and not re.search(r"[.!?:]$", merged[-1])
        ):
            merged[-1] += " " + line
        else:
            merged.append(line)

    lines = merged
    units = []

    for i, line in enumerate(lines):
        if not line:
            continue

        if len(line.split()) >= 8:
            units.extend(
                sentence.strip()
                for sentence in re.split(r"(?<=[.!?])\s+", line)
                if sentence.strip()
            )
        elif re.search(r"[A-Za-z]{3}", line):
            window = [line]

            for following in lines[i + 1:i + 4]:
                if not following or len(following.split()) >= 8:
                    break
                window.append(following)

            units.append(" ".join(window))

    return units


def _numbers(text):
    """Extract numeric values while ignoring fiscal-quarter/year labels."""
    text = re.sub(
        r"\b(?:Q[1-4]|H[12]|FY\s?\d{2,4})\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"(?<![$\d,.])(?:19|20)\d{2}(?![\d,]|\.\d|\s*(?:million|billion|%|percent))",
        " ",
        text,
    )
    return {
        number.replace(",", "").rstrip(".")
        for number in re.findall(r"\d[\d,]*\.?\d*", text)
    }


def _unsupported_numbers(answer, cited):
    """Return answer numbers that do not appear in the cited evidence."""
    cited_numbers = (
        set().union(*[_numbers(quote) for quote in cited])
        if cited
        else set()
    )
    return sorted(number for number in _numbers(answer) if number not in cited_numbers)


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
    """Answer a question using retrieved source text and validated citations."""
    vectors, meta = build_index(text, doc_id)
    hits = search(question, vectors, meta, k=k)

    units = []
    seen = set()

    for hit in hits:
        for unit in make_units(hit["text"]):
            if unit not in seen:
                seen.add(unit)
                units.append(unit)

    context = "\n".join(
        f"[S{index + 1}] {unit}"
        for index, unit in enumerate(units)
    )
    user = f"QUESTION: {question}\n\nNUMBERED SENTENCES:\n{context}"
    system = SYSTEM.replace(
        "{schema}",
        json.dumps(ModelOut.model_json_schema()),
    )

    out, retries = ask_json(system, user, ModelOut)

    if not out.answerable:
        retry_output, _ = ask_json(system, user, ModelOut)
        if retry_output.answerable:
            out = retry_output

    if len(out.support_ids) > 5:
        out, retries = ask_json(
            system,
            user + "\n\nREMINDER: support_ids must contain at most 3 IDs.",
            ModelOut,
        )

    issues = []
    citations = []

    for support_id in out.support_ids[:3]:
        match = re.fullmatch(r"S?(\d+)", support_id.strip())

        if match and 1 <= int(match.group(1)) <= len(units):
            unit = units[int(match.group(1)) - 1]
            if unit not in citations:
                citations.append(unit)
        else:
            issues.append(f"unknown support id ignored: {support_id}")

    source = _norm(clean_text(text))
    citations = [
        quote for quote in citations
        if _norm(quote) in source
    ]

    answer = out.answer

    if not out.answerable:
        answer = NOT_FOUND
        citations = []
    elif not citations:
        answer = NOT_FOUND
        issues.append("no valid citation; answer replaced with not-found")
    elif not _has_lexical_support(out.answer, citations):
        issues.append("citation text does not lexically support the answer")
        answer = NOT_FOUND
        citations = []
    else:
        bad_numbers = _unsupported_numbers(out.answer, citations)

        if bad_numbers:
            answer_words = set(
                re.findall(r"[a-z]{3,}", out.answer.lower())
            )

            # Try adding source sentences that contain missing figures and
            # share meaningful terms with the answer.
            for unit in units:
                if len(citations) >= 3:
                    break
                if unit in citations or _norm(unit) not in source:
                    continue
                if not any(number in _numbers(unit) for number in bad_numbers):
                    continue

                unit_words = set(re.findall(r"[a-z]{3,}", unit.lower()))
                if len(answer_words & unit_words) >= 2:
                    citations.append(unit)

            bad_numbers = _unsupported_numbers(out.answer, citations)

        if bad_numbers:
            issues.append(
                "numbers in the answer not found in its citations: "
                + ", ".join(bad_numbers)
            )
            answer = NOT_FOUND
            citations = []

    result = AnalystAnswer(
        answer=answer,
        citations=[
            Citation(doc_id=doc_id, quote=quote)
            for quote in citations
        ],
    )

    return {
        "result": result.model_dump(),
        "issues": issues,
        "retries": retries,
        "retrieved": [
            {
                "chunk_id": hit["chunk_id"],
                "score": round(hit["score"], 3),
            }
            for hit in hits
        ],
    }


from .normalize import normalize_pdf_text as _normalize_pdf_text

_answer_question_raw = answer_question


def answer_question(question, text, doc_id="doc", k=5):
    """Normalize extracted PDF text before running the analyst."""
    return _answer_question_raw(
        question,
        _normalize_pdf_text(text),
        doc_id=doc_id,
        k=k,
    )
