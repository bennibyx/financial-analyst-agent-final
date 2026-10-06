# agents/verify_source.py
# Second hallucination check: every metric value must appear in the SOURCE chunk text,
# not just in the quote the model wrote. Also rejects "percent" values for absolute amounts.
import re

# Metrics that are money amounts, never percentages
ABSOLUTE_NAMES = {"revenue", "net_income", "free_cash_flow", "operating_income", "eps"}

def number_in_source(value, text):
    """True if value appears in text as a standalone number (with or without thousands commas)."""
    if value is None:
        return True
    forms = {f"{value:g}", f"{value:.1f}", f"{value:.2f}"}
    if float(value).is_integer():
        forms.add(f"{int(value):,}")      # 215938 -> 215,938
        forms.add(str(int(value)))        # 215938
    else:
        forms.add(f"{value:,.1f}")
    for f in forms:
        # lookbehind/lookahead stop "26,000" from matching inside "126,000" or "26,0001"
        if re.search(r"(?<![\d,.])" + re.escape(f) + r"(?!\d|,\d)", text):
            return True
    return False

def check_against_source(result, text):
    """Drop metrics whose value is not in the source text. Returns (result, issues)."""
    issues, kept = [], []
    for m in result.metrics:
        if m.value is not None and m.unit == "percent" and m.name in ABSOLUTE_NAMES:
            issues.append(f"metric:{m.name}: percent unit on an absolute amount, dropped")
        elif not number_in_source(m.value, text):
            issues.append(f"metric:{m.name}: value {m.value} not found in source, dropped")
        else:
            kept.append(m)
    result.metrics = kept
    return result, issues
