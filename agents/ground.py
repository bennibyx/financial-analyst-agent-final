# agents/ground.py -- replace the model's quote with the real source line (done in code, not by the LLM)
import re
from .verify_source import _forms, _pattern
from .normalize import clean_quote

# words that must be on the SAME line as the number
NEED = {
    "revenue": ["revenue"],
    "net_income": ["net income"],
    "operating_income": ["operating income"],
    "gross_margin": ["gross margin", "gross profit"],
    "operating_margin": ["operating margin", "operating income"],
    "eps": ["diluted"],              # diluted EPS only, never basic
    "free_cash_flow": ["free cash flow"],
}

def _find_line(value, name, text):
    need = NEED.get(name)
    for ln in text.split("\n"):
        if not any(re.search(_pattern(f), ln) for f in _forms(value)):
            continue
        if need is None or any(w in ln.lower() for w in need):
            return ln
    return None

def ground_quotes(result, text):
    """Set each metric's source_quote to the real line holding its number. Drops basic-EPS mistakes."""
    kept, issues = [], []
    for m in result.metrics:
        if m.value is None:
            kept.append(m)
            continue
        line = _find_line(m.value, m.name, text)
        if line:
            m.source_quote = clean_quote(line)
        else:
            issues.append(f"metric:{m.name}: {m.value} not on a line with its label (segment/other row?), dropped")
            continue
        kept.append(m)
    result.metrics = kept
    return result, issues

# ---- table fallback: model skipped a headline number, so read it straight from the table row ----
from .schemas import Metric

_OPINC = re.compile(r"^\s*operating income\s+\$?\s*([\d,]{5,})(?:\s|$)", re.I)   # needs 5+ digits: skips "60.4 62.4" margin rows

def table_fallback(text, metrics):
    """Add operating_income from its table row if missing. Cross-checked against revenue and operating_margin."""
    have = {m.name for m in metrics}
    rev = next((m for m in metrics if m.name == "revenue" and m.value), None)
    opm = next((m for m in metrics if m.name == "operating_margin" and m.value is not None), None)
    added = []
    if "operating_income" not in have and rev:
        for ln in text.split("\n"):
            hit = _OPINC.match(ln)
            if not hit:
                continue
            val = float(hit.group(1).replace(",", ""))
            if opm and abs(val / rev.value * 100 - opm.value) > 1.0:
                print(f"   FALLBACK rejected operating_income {val}: does not match margin {opm.value}%", flush=True)
                continue
            added.append(Metric(name="operating_income", basis=None, value=val, unit="USD_million",
                                period=rev.period, source_quote=clean_quote(ln)))
            print(f"   FALLBACK added operating_income {val} from table row", flush=True)
            break
    return added

# ---- one unit for all money: USD_million, using the exact table figure when it matches ----
_LABEL = {"revenue": "revenue", "net_income": "net income", "operating_income": "operating income"}

def upgrade_units(text, metrics):
    """A value in USD_billion becomes USD_million. If a table row matches it (within rounding), use the exact row value."""
    for m in metrics:
        if m.unit != "USD_billion" or m.value is None or m.name not in _LABEL:
            continue
        exact = None
        for ln in text.split("\n"):
            hit = re.match(r"^\s*" + _LABEL[m.name] + r"\s+\$?\s*([\d,]{5,})(?:\s|$)", ln, re.I)
            if hit:
                v = float(hit.group(1).replace(",", ""))
                if abs(v / 1000 - m.value) <= 0.06:      # 215,938 vs 215.9 (rounded)
                    exact = (v, ln)
                    break
        if exact:
            m.value, m.source_quote = exact[0], clean_quote(exact[1])
        else:
            m.value = round(m.value * 1000, 3)
        m.unit = "USD_million"
    return metrics

# ---- operating margin from its table row, cross-checked against operating income / revenue ----
def margin_fallback(text, metrics):
    rev = next((m for m in metrics if m.name == "revenue" and m.value), None)
    oi = next((m for m in metrics if m.name == "operating_income" and m.value), None)
    if any(m.name == "operating_margin" for m in metrics) or not (rev and oi):
        return []
    expected = oi.value / rev.value * 100
    for ln in text.split("\n"):
        hit = re.match(r"^\s*operating income\s+(\d{1,2}\.\d)\s+(\d{1,2}\.\d)", ln, re.I)
        if hit and abs(float(hit.group(1)) - expected) <= 1.0:
            print(f"   FALLBACK added operating_margin {hit.group(1)} (matches {expected:.1f}% from income/revenue)", flush=True)
            return [Metric(name="operating_margin", basis=None, value=float(hit.group(1)), unit="percent",
                           period=rev.period, source_quote=clean_quote(ln))]
    return []

# ---- headline numbers straight from table rows (deterministic safety net, no LLM) ----
_ROWS = {
    "revenue":          (r"^\s*(?:total\s+)?revenue\s+\$?\s*([\d,]{5,})(?:\s|$)", "USD_million"),
    "net_income":       (r"^\s*net income\s+\$?\s*([\d,]{5,})(?:\s|$)", "USD_million"),
    "operating_income": (r"^\s*operating income\s+\$?\s*([\d,]{5,})(?:\s|$)", "USD_million"),
    "eps":              (r"^\s*(?:diluted|net income per diluted share)\s+\$?\s*(\d{1,3}\.\d{2})(?:\s|$)", "USD"),
}

def headline_fallback(text, metrics):
    """Fill revenue / net income / operating income / diluted EPS from their table rows if the model missed them."""
    have = {m.name for m in metrics}
    period = next((m.period for m in metrics if m.period), None)
    if not period:
        y = re.search(r"fiscal year (\d{4})", text, re.I)
        period = f"Fiscal Year {y.group(1)}" if y else None
    if not period:
        return []
    sent = re.search(r"revenue for fiscal year \d{4} was \$([\d.]+) billion", text, re.I)
    rev_hint = float(sent.group(1)) if sent else None          # "$215.9 billion" sentence = cross-check
    rev = next((m.value for m in metrics if m.name == "revenue" and m.value), None)
    added = []
    for name, (pat, unit) in _ROWS.items():
        if name in have:
            continue
        for ln in text.split("\n"):
            hit = re.match(pat, ln, re.I)
            if not hit:
                continue
            v = float(hit.group(1).replace(",", ""))
            if name == "revenue" and rev_hint and abs(v / 1000 - rev_hint) > 0.06:
                continue                                       # not the annual total
            if name in ("net_income", "operating_income") and rev and v >= rev:
                continue                                       # profit can't exceed revenue
            added.append(Metric(name=name, basis=None, value=v, unit=unit, period=period,
                                source_quote=clean_quote(ln)))
            if name == "revenue":
                rev = v
            print(f"   FALLBACK added {name} {v} from table row", flush=True)
            break
    return added

# ---- cross-checks that catch wrong margins ----
def fix_margin(text, metrics):
    """operating_margin must match operating_income / revenue (within 0.5 points), else drop it."""
    rev = next((m for m in metrics if m.name == "revenue" and m.value), None)
    oi = next((m for m in metrics if m.name == "operating_income" and m.value), None)
    om = next((m for m in metrics if m.name == "operating_margin" and m.value is not None), None)
    if rev and oi and om:
        expected = oi.value / rev.value * 100
        if abs(om.value - expected) > 0.5:
            print(f"   DROPPED: operating_margin {om.value} disagrees with operating_income/revenue ({expected:.1f}%)", flush=True)
            return [m for m in metrics if m is not om]
    return metrics

def gross_fallback(text, metrics):
    """Fill gross_margin from its percent row ('Gross margin 71.1 % 75.0 %') if the model missed it."""
    rev = next((m for m in metrics if m.name == "revenue"), None)
    if any(m.name == "gross_margin" for m in metrics) or not rev:
        return []
    for ln in text.split("\n"):
        hit = re.match(r"^\s*gross (?:margin|profit)\s+(\d{2}\.\d)\s*%?\s+\d{2}\.\d", ln, re.I)
        if hit:
            print(f"   FALLBACK added gross_margin {hit.group(1)} from table row", flush=True)
            return [Metric(name="gross_margin", basis=None, value=float(hit.group(1)), unit="percent",
                           period=rev.period, source_quote=clean_quote(ln))]
    return []
