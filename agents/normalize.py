# agents/normalize.py -- period format, quote cleanup, chunk ranking
import re

PERIOD_RE = re.compile(r"\bQ([1-4])\W*(?:FY|fiscal)?\s*(\d{4}|\d{2})\b", re.I)

YEAR_ENDED_RE = re.compile(r"\byear\s+ended\s+\w+\s+\d{1,2},\s*(\d{4})", re.I)

def normalize_period(raw):
    """'Q4 FY26', 'q4 fy2026', 'Q4 2026' -> 'Q4 2026'. Full-year labels pass through unchanged."""
    if not isinstance(raw, str):
        return raw
    def fix(m):
        yr = m.group(2)
        yr = "20" + yr if len(yr) == 2 else yr
        return f"Q{m.group(1)} {yr}"
    y = YEAR_ENDED_RE.search(raw)
    if y:
        return f"Fiscal Year {y.group(1)}"   # NVIDIA-style: fiscal year named by its end year
    return PERIOD_RE.sub(fix, raw, count=1)

def clean_quote(text):
    """Remove stray PDF table pipes and extra spaces from a quote."""
    return re.sub(r"\s+", " ", re.sub(r"\s*\|\s*", " ", text or "")).strip()

def quote_in_source(quote, source):
    """Hallucination check: is the quote really in the source (ignoring pipes/spacing)?"""
    return clean_quote(quote).lower() in clean_quote(source).lower()

KEYWORDS = ("revenue", "net income", "earnings per share", "eps",
            "gross margin", "operating income", "guidance", "outlook")

def pick_chunks(chunks, max_chunks=8):
    """Keep the most finance-heavy chunks (strings or objects with .text), in document order."""
    def score(c):
        t = getattr(c, "text", c).lower()
        return sum(k in t for k in KEYWORDS) + (0.5 if re.search(r"\$\s?\d", t) else 0)
    top = sorted(range(len(chunks)), key=lambda i: score(chunks[i]), reverse=True)[:max_chunks]
    return [chunks[i] for i in sorted(top)]

if __name__ == "__main__":
    assert normalize_period("Q4 FY26") == "Q4 2026"
    assert normalize_period("Q4 2026") == "Q4 2026"
    assert normalize_period("Q1 FY2027") == "Q1 2027"
    assert normalize_period("fiscal year 2027") == "fiscal year 2027"
    assert quote_in_source("revenue | of $44.1 billion", "Revenue of $44.1 billion")
    assert not quote_in_source("revenue of $99 billion", "Revenue of $44.1 billion")
    assert len(pick_chunks(["intro", "Revenue was $5", "legal"], 1)) == 1
    print("normalize.py OK")

def normalize_pdf_text(text):
    out = []
    for ln in text.split("\n"):
        if "|" in ln:
            ln = ln.replace("|", " ")
            ln = re.sub(r"[ \t]+", " ", ln).strip()
            ln = re.sub(r"^\(\s*\$?\s*in millions[^)]*\)\s*", "", ln, flags=re.I)
        out.append(ln)
    return "\n".join(out)


def strip_page_furniture(text):
    """Remove repeating page headers/footers (FactSet CallStreet transcripts only)."""
    if "callstreet" not in text.lower():
        return text
    lines = text.split("\n")
    counts = {}
    for ln in lines:
        k = ln.strip()
        if k:
            counts[k] = counts.get(k, 0) + 1
    furniture = {k for k, n in counts.items() if n >= 5 and len(k) <= 100}
    out, prev_was_factset = [], False
    for ln in lines:
        k = ln.strip()
        low = k.lower()
        is_factset = "factset" in low or "callstreet" in low or low.startswith("copyright")
        if k in furniture or is_factset:
            prev_was_factset = is_factset or prev_was_factset
            continue
        if prev_was_factset and re.fullmatch(r"\d{1,3}", k):
            prev_was_factset = False
            continue
        prev_was_factset = False
        out.append(ln)
    return "\n".join(out)


_normalize_pdf_text_v1 = normalize_pdf_text

def normalize_pdf_text(text):
    return _normalize_pdf_text_v1(strip_page_furniture(text))
