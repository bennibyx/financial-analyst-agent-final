# agents/verify.py -- cheap hallucination checks (v3)
import re, difflib

STRONG = re.compile(r"copyright ©|factset|callstreet|corrected transcript", re.I)
SHORT = re.compile(r"^(nvidia corp\. )?\(nvda\)$|earnings call$|^\d{1,3}$|^total pages|^\d{1,2}-[a-z]{3}-\d{4}$", re.I)

def clean_text(text):
    """Drop PDF page headers/footers. Quick fix for FactSet-style PDFs only."""
    keep = []
    for line in text.splitlines():
        s = line.strip()
        if STRONG.search(s) or (len(s) <= 40 and SHORT.search(s)):
            continue
        keep.append(line)
    return "\n".join(keep)

def _norm(s):
    return " ".join(s.split()).lower()

def sentences(text):
    return re.split(r"(?<=[.!?])\s+", " ".join(text.split()))

def snap_quote(quote, sents):
    """Return the exact transcript sentence for a quote (exact, else fuzzy >= 0.85)."""
    q = _norm(quote).rstrip(".!? ")
    if not q:
        return None
    for s in sents:
        if q in _norm(s):
            return s
    best, best_r = None, 0.0
    for s in sents:
        if not (0.5 * len(q) <= len(s) <= 2 * len(q) + 50):
            continue
        r = difflib.SequenceMatcher(None, q, _norm(s)).ratio()
        if r > best_r:
            best, best_r = s, r
    return best if best_r >= 0.85 else None

def number_in_quote(value, quote):
    if value is None:
        return True
    return any(f in quote for f in {f"{value:g}", f"{value:.1f}"})

def verify(result, text):
    """Fix quotes/basis/numbers using the source. Returns (result, issues, fixes)."""
    sents = sentences(text)
    issues, fixes = [], []
    for m in result.metrics:                      # a null metric has no basis
        if m.value is None and m.basis:
            m.basis = None
    items = [("metric:" + m.name, m, ["value", "yoy_change_pct", "qoq_change_pct"]) for m in result.metrics]
    items += [("guidance:" + g.metric + ":" + str(g.basis), g,
               ["midpoint", "low", "high"]) for g in result.guidance]
    for label, item, fields in items:
        nums = [getattr(item, f) for f in fields]
        if not item.source_quote.strip():
            if any(n is not None for n in nums):
                issues.append(f"{label}: value without a quote")
            continue
        snapped = snap_quote(item.source_quote, sents)
        if snapped is None:
            issues.append(f"{label}: quote not found in source")
            continue
        if _norm(snapped) != _norm(item.source_quote):
            fixes.append(f"{label}: quote snapped to exact sentence")
        item.source_quote = snapped
        if item.basis and "gaap" not in snapped.lower():
            fixes.append(f"{label}: basis removed (not stated in quote)")
            item.basis = None
        for f in fields:
            n = getattr(item, f)
            if n is not None and not number_in_quote(n, snapped):
                if label.startswith("guidance"):
                    setattr(item, f, None)        # unsupported number: remove it
                    fixes.append(f"{label}: unsupported {f}={n} removed")
                else:
                    issues.append(f"{label}: number {n} not in its quote")
    return result, issues, fixes
