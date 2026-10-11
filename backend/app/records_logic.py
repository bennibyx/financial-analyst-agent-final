"""Pure helpers for the records API (no database, no web code)."""
import re
from typing import Optional

MONEY_TOTALS = {"revenue", "operating_income", "net_income", "free_cash_flow"}
DOC_RANK = {"10-Q": 0, "10-K": 0, "commentary": 1, "transcript": 2, "news": 3}
BASIS_RANK = {"GAAP": 0, None: 1, "non-GAAP": 2}
CONFLICT_TOLERANCE_PCT = 2.0

# Order matters: "_non_gaap" must be checked before "_gaap".
_BASIS_SUFFIXES = (("_non_gaap", "non-GAAP"), ("_gaap", "GAAP"))

_QUARTER_FIRST = re.compile(
    r"q\s*([1-4])\s*[-_ ]?\s*(?:fy|fiscal(?:\s+year)?)?\s*[-_ ]?\s*(\d{4}|\d{2})\b", re.I
)
_YEAR_FIRST = re.compile(
    r"(?:fy|fiscal(?:\s+year)?)\s*[-_ ]?\s*(\d{4}|\d{2})\s*[-_ ]?\s*q\s*([1-4])\b", re.I
)


def parse_metric_name(name: str) -> tuple[str, Optional[str]]:
    """'gross_margin_non_gaap' -> ('gross_margin', 'non-GAAP'); 'revenue' -> ('revenue', None)."""
    for suffix, basis in _BASIS_SUFFIXES:
        if name.endswith(suffix):
            return name[: -len(suffix)], basis
    return name, None


def normalize_period(raw: Optional[str]) -> Optional[str]:
    """'Q2 fiscal 2027' / 'Q2 FY27' / 'Q2FY27' -> 'Q2 FY27'. Returns None if not recognised."""
    if not raw:
        return None
    s = raw.strip()
    m = _QUARTER_FIRST.search(s)
    if m:
        q, y = m.group(1), m.group(2)
    else:
        m = _YEAR_FIRST.search(s)
        if not m:
            return None
        y, q = m.group(1), m.group(2)
    return f"Q{q} FY{int(y) % 100:02d}"


def period_sort_key(period: str) -> tuple[int, int]:
    """Chronological order: Q4 FY26 < Q1 FY27 < Q2 FY27. Unknown periods sort last."""
    m = re.fullmatch(r"Q(\d) FY(\d\d)", period)
    return (int(m.group(2)), int(m.group(1))) if m else (999, 0)


def normalize_value(base: str, value: Optional[float], unit: Optional[str]):
    """Convert billions to millions for money totals so values can be compared."""
    if value is None:
        return None, unit
    if base in MONEY_TOTALS and unit == "USD_billion":
        return round(value * 1000, 3), "USD_million"
    return value, unit


def build_records(rows: list[dict]) -> list[dict]:
    """rows: dicts with id, name, value, unit, period, document_id, doc_type, filename.
    Returns cleaned records: split basis, canonical period, comparable units, no duplicates."""
    seen, out = set(), []
    for r in rows:
        if r.get("value") is None:
            continue
        base, basis = parse_metric_name(r["name"])
        period = normalize_period(r.get("period")) or (r.get("period") or "unknown")
        value, unit = normalize_value(base, r["value"], r.get("unit"))
        key = (r["document_id"], base, basis, period, value)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "id": r["id"], "document_id": r["document_id"], "filename": r.get("filename"),
            "doc_type": r.get("doc_type"), "metric": base, "basis": basis,
            "period": period, "period_raw": r.get("period"),
            "value": value, "unit": unit,
            "original_value": r["value"], "original_unit": r.get("unit"),
        })
    return out


def basis_compatible(a: Optional[str], b: Optional[str]) -> bool:
    """Unlabeled matches anything; GAAP never matches non-GAAP."""
    return a is None or b is None or a == b


def choose(records: list[dict], basis: Optional[str] = None):
    """records: cleaned records for ONE metric in ONE period.
    Returns (best_record_or_None, conflicting_records)."""
    def rank(b):
        return 0 if basis and b == basis else BASIS_RANK[b]

    cands = [r for r in records if basis is None or r["basis"] in (None, basis)]
    if not cands:
        return None, []
    cands = sorted(cands, key=lambda r: (rank(r["basis"]), DOC_RANK.get(r["doc_type"], 9), r["id"]))
    best = cands[0]
    conflicts = []
    for r in cands[1:]:
        if not basis_compatible(best["basis"], r["basis"]):
            continue
        if best["value"]:
            diff = abs(r["value"] - best["value"]) / abs(best["value"]) * 100
        else:
            diff = 0.0 if r["value"] == 0 else 100.0
        if diff > CONFLICT_TOLERANCE_PCT:
            conflicts.append(r)
    return best, conflicts
