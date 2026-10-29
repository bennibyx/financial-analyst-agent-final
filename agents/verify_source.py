
# agents/verify_source.py
# Second hallucination check: verify numeric values against source text
# and require appropriate metric labels for key financial metrics.

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
}

# A matching number must appear on the same line as a label,
# or within the two preceding lines.
LABELS = {
    "gross_margin": ["gross margin", "gross profit"],
    "operating_margin": ["operating margin", "operating income"],
    "net_income": ["net income"],
    "operating_income": ["operating income"],
    "revenue": ["revenue"],
}


def _forms(value):
    """Generate common textual representations of a numeric value."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return set()

    forms = {f"{number:g}", f"{number:.1f}", f"{number:.2f}"}
    for scaled in (number / 1000, number * 1000):
        forms.update({f"{scaled:g}", f"{scaled:.1f}", f"{scaled:.2f}"})

    if number.is_integer():
        forms.add(f"{int(number):,}")
        forms.add(str(int(number)))
    else:
        forms.add(f"{number:,.1f}")

    return forms


def _pattern(form):
    """Match a complete number, not part of a larger number or decimal."""
    return (
        r"(?<![\d.,])"
        + re.escape(form)
        + r"(?!\d|,\d|\.\d)"
    )


def number_in_source(value, text, labels=None):
    """
    Check whether a standalone number occurs in the source.

    If labels are supplied, require at least one label on the same line
    or within the two preceding lines. This supports common financial
    tables where labels and values occupy adjacent lines.
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
            if not re.search(pattern, line):
                continue

            window = " ".join(
                lines[max(0, index - 2):index + 1]
            ).lower()

            if any(label.lower() in window for label in labels):
                return True

    return False


def check_against_source(result, text):
    """
    Remove metrics whose values cannot be verified against the source.

    For revenue, net income, gross margin and operating margin, check
    that the relevant label is near the reported number.

    Rescue amounts accidentally expressed in billions when the source
    contains the equivalent amount in millions.
    """
    issues = []
    kept = []

    metrics = getattr(result, "metrics", [])

    revenue_metric = next(
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
        # A percentage above 100 is generally invalid. Gross profit
        # mistakenly reported as a percentage may be recoverable.
        if (
            metric.unit == "percent"
            and metric.value is not None
            and abs(metric.value) > 100
        ):
            derived = None

            if (
                metric.name == "gross_margin"
                and revenue_metric is not None
                and revenue_metric.value
                and 0 < metric.value < revenue_metric.value
            ):
                derived = round(
                    metric.value / revenue_metric.value * 100,
                    1,
                )

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

        # Gross margin must be a percentage. A large non-percent value here is gross profit:
        # convert it with revenue when revenue is known, otherwise drop it.
        if (
            metric.name == "gross_margin"
            and metric.value is not None
            and metric.unit != "percent"
            and abs(metric.value) > 100
        ):
            if (
                revenue_metric is not None
                and revenue_metric.value
                and 0 < metric.value < revenue_metric.value
            ):
                derived = round(metric.value / revenue_metric.value * 100, 1)
                issues.append(
                    f"FIXED metric:gross_margin: {metric.value} is gross profit, "
                    f"not a percent; computed {derived}% from amount/revenue"
                )
                metric.value = derived
                metric.unit = "percent"
                kept.append(metric)
            else:
                issues.append(
                    f"metric:gross_margin: amount {metric.value} is not a percent "
                    f"and revenue is unknown, dropped"
                )
            continue

        # Require labels for metrics with explicit label definitions.
        labels = LABELS.get(metric.name)

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

        # Preserve the existing billions-to-millions recovery behavior.
        fixed = (
            round(metric.value * 1000, 3)
            if metric.value is not None
            else None
        )

        if (
            metric.name in RESCALE_NAMES
            and metric.unit != "percent"
            and fixed
            and number_in_source(fixed, text, labels)
        ):
            issues.append(
                f"RESCUED metric:{metric.name}: {metric.value} "
                f"-> {fixed} (found in source with matching label)"
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
