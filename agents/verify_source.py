
# agents/verify_source.py
# Second hallucination check. A value must appear in the source text and,
# for margins, appear near a line carrying the metric's label.

import re


ABSOLUTE_NAMES = {
    "revenue",
    "net_income",
    "free_cash_flow",
    "operating_income",
    "eps",
}

RESCALE_NAMES = {
    "revenue",
    "net_income",
    "free_cash_flow",
    "operating_income",
}  # EPS is never rescaled.

LABELS = {
    "gross_margin": ["gross margin", "gross profit"],
    "operating_margin": ["operating margin", "operating income"],
    "net_income": ["net income"],
    "revenue": ["revenue"],
}


def _forms(value):
    """Generate common textual representations of a numeric value."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return set()

    forms = {f"{number:g}", f"{number:.1f}", f"{number:.2f}"}

    if number.is_integer():
        forms.add(f"{int(number):,}")
        forms.add(str(int(number)))
    else:
        forms.add(f"{number:,.1f}")

    return forms


def _pattern(f):
    """Match a complete number, not a substring of a larger number."""
    return (
        r"(?<![\d.,])"
        + re.escape(f)
        + r"(?!\d|,\d|\.\d)"
    )


def number_in_source(value, text, labels=None):
    """
    Return True if a numeric value appears as a standalone number in text.

    If labels are provided, require a matching label on the same line or
    within the two preceding lines. This accommodates financial tables
    where labels and values may be separated across lines.
    """
    if value is None:
        return True

    if not isinstance(text, str):
        return False

    lines = text.splitlines()

    for form in _forms(value):
        pattern = _pattern(form)

        if labels is None:
            if re.search(pattern, text):
                return True
            continue

        for index, line in enumerate(lines):
            if re.search(pattern, line):
                window = " ".join(
                    lines[max(0, index - 2):index + 1]
                ).lower()

                if any(label.lower() in window for label in labels):
                    return True

    return False


def check_against_source(result, text):
    """
    Remove unsupported extracted metrics.

    Rescue amounts that appear to have been converted from billions
    to millions by checking whether value * 1000 occurs in the source.
    Returns (result, issues).
    """
    issues = []
    kept = []

    metrics = getattr(result, "metrics", [])

    rev = next(
        (
            metric
            for metric in metrics
            if metric.name == "revenue"
            and metric.value
            and metric.unit != "percent"
        ),
        None,
    )

    for metric in metrics:
        # Percentages greater than 100 are generally invalid.
        # A gross-profit amount may have been mistakenly labelled as a
        # percentage; if possible, calculate its margin using revenue.
        if (
            metric.unit == "percent"
            and metric.value is not None
            and abs(metric.value) > 100
        ):
            derived = None

            if (
                metric.name == "gross_margin"
                and rev is not None
                and rev.value
                and 0 < metric.value < rev.value
            ):
                derived = round(metric.value / rev.value * 100, 1)

            if derived is None:
                issues.append(
                    f"metric:{metric.name}: percent value "
                    f"{metric.value} impossible (>100), dropped"
                )
                continue

            issues.append(
                f"FIXED metric:{metric.name}: {metric.value} is an "
                f"amount, not a percent; computed {derived}% "
                f"from amount/revenue"
            )
            metric.value = derived
            kept.append(metric)
            continue

        labels = (
            LABELS.get(metric.name)
            if metric.name in ("gross_margin", "operating_margin")
            else None
        )

        if (
            metric.value is not None
            and metric.unit == "percent"
            and metric.name in ABSOLUTE_NAMES
        ):
            issues.append(
                f"metric:{metric.name}: percent unit on an "
                f"absolute amount, dropped"
            )
            continue

        if number_in_source(metric.value, text, labels):
            kept.append(metric)
            continue

        fixed = (
            round(metric.value * 1000, 3)
            if metric.value is not None
            else None
        )

        if (
            metric.name in RESCALE_NAMES
            and metric.unit != "percent"
            and fixed
            and number_in_source(fixed, text)
        ):
            issues.append(
                f"RESCUED metric:{metric.name}: {metric.value} "
                f"-> {fixed} (found in source)"
            )
            metric.value = fixed
            metric.unit = "USD_million"
            kept.append(metric)
        else:
            why = (
                "not found next to its label"
                if labels
                else "not found in source"
            )
            issues.append(
                f"metric:{metric.name}: value {metric.value} "
                f"{why}, dropped"
            )

    result.metrics = kept
    return result, issues
