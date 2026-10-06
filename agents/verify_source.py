# agents/verify_source.py
# Second hallucination check. A value must (1) appear in the SOURCE chunk text and, for margins,
# (2) appear on a line that carries the metric's label (stops "$60.0 billion buyback" passing as a margin).
import re

ABSOLUTE_NAMES = {"revenue", "net_income", "free_cash_flow", "operating_income", "eps"}
RESCALE_NAMES = {"revenue", "net_income", "free_cash_flow", "operating_income"}   # eps never rescaled

# Words that must appear on the same line as the number, per metric
LABELS = {
    "gross_margin": ["gross margin", "gross profit"],
    "operating_margin": ["operating margin", "operating income"],
    "net_income": ["net income"],
    "revenue": ["revenue"],
}

def _forms(value):
    forms = {f"{value:g}", f"{value:.1f}", f"{value:.2f}"}
    if float(value).is_integer():
        forms.add(f"{int(value):,}")      # 215938 -> 215,938
        forms.add(str(int(value)))
    else:
        forms.add(f"{value:,.1f}")
    return forms

def _pattern(f):
    # lookbehind/lookahead stop "26,000" matching inside "126,000" or "26,0001"
    return r"(?<![\d,.])" + re.escape(f) + r"(?!\d|,\d)"

def number_in_source(value, text, labels=None):
    """True if value appears as a standalone number; if labels given, on a line containing one of them."""
    if value is None:
        return True
    lines = text.split("\n")
    for f in _forms(value):
        pat = _pattern(f)
        if labels is None:
            if re.search(pat, text):
                return True
        else:
            for ln in lines:
                if re.search(pat, ln) and any(l in ln.lower() for l in labels):
                    return True
    return False

def check_against_source(result, text):
    """Drop metrics whose value is not in the source (label-aware). Returns (result, issues).
    Rescue: money amount missing but value x 1000 present (model converted millions to billions)
    -> correct value AND unit instead of dropping."""
    issues, kept = [], []
    for m in result.metrics:
        labels = LABELS.get(m.name) if m.name in ("gross_margin", "operating_margin") else None
        if m.value is not None and m.unit == "percent" and m.name in ABSOLUTE_NAMES:
            issues.append(f"metric:{m.name}: percent unit on an absolute amount, dropped")
        elif number_in_source(m.value, text, labels):
            kept.append(m)
        else:
            fixed = round(m.value * 1000, 3) if m.value is not None else None
            if m.name in RESCALE_NAMES and m.unit != "percent" and fixed and number_in_source(fixed, text):
                issues.append(f"RESCUED metric:{m.name}: {m.value} -> {fixed} (found in source)")
                m.value = fixed
                m.unit = "USD_million"          # the source table is in millions
                kept.append(m)
            else:
                why = "not found next to its label" if labels else "not found in source"
                issues.append(f"metric:{m.name}: value {m.value} {why}, dropped")
    result.metrics = kept
    return result, issues
