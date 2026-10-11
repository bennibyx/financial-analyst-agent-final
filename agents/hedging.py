import re

STRONG_RE = re.compile(
    r"\b(too early|very tight|uncertain|uncertainty|no assurance|"
    r"hard to predict|difficult to (?:predict|say)|hope)\b", re.I)
WEAK_RE = re.compile(r"\b(could|may|might|depends|depending)\b", re.I)
BOILER_RE = re.compile(
    r"forward[- ]looking|you may begin|safe harbor|risks and uncertainties|factors that could|"
    r"actual results|non-gaap (?:measures|financial)|reconcil|conference", re.I)


def hedging_stats(text):
    flat = re.sub(r"\s+", " ", text)
    words = len(flat.split())
    sents = [s.strip() for s in re.split(r"(?<=[.!])\s+", flat)
             if 40 <= len(s) <= 400 and "?" not in s and not BOILER_RE.search(s)]
    strong = [s for s in sents if STRONG_RE.search(s)]
    weak = [s for s in sents if WEAK_RE.search(s) and not STRONG_RE.search(s)]
    per = lambda n: round(n / words * 1000, 2) if words else 0.0
    return {"words": words, "strong": strong, "weak_count": len(weak),
            "strong_per_1000": per(len(strong)), "weak_per_1000": per(len(weak))}


def load(path):
    raw = open(path, "rb").read()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


if __name__ == "__main__":
    import sys
    from .normalize import normalize_pdf_text
    for f in sys.argv[1:]:
        st = hedging_stats(normalize_pdf_text(load(f)))
        print(f"\n=== {f}")
        print(f"words: {st['words']} | STRONG hedges: {len(st['strong'])} ({st['strong_per_1000']}/1000 words) | weak modals: {st['weak_count']} ({st['weak_per_1000']}/1000)")
        for s in st["strong"][:8]:
            print("  -", s[:170])
