
import re


def clean_text(text):
    """Normalize text before checking extracted financial claims."""
    if text is None:
        return ""
    return str(text).strip()


def number_in_quote(value, quote):
    """Return True only when the complete number appears in the quote."""
    if value is None:
        return True

    quote = clean_text(quote)

    try:
        forms = {f"{value:g}", f"{value:.1f}"}
    except (TypeError, ValueError):
        return False

    for form in forms:
        pattern = (
            r"(?<![\d.,])"
            + re.escape(form)
            + r"(?!\d|,\d|\.\d)"
        )
        if re.search(pattern, quote):
            return True

    return False


def verify(result, text):
    """
    Verify extracted financial metrics and guidance against their quotes.

    Returns:
        result: The checked extraction result.
        issues: Claims that could not be verified.
        fixes: Corrections applied during verification.
    """
    issues = []
    fixes = []

    if not isinstance(result, dict):
        return result, ["Extraction result is not a dictionary"], fixes

    source_text = clean_text(text)

    # Check financial metrics.
    metrics = result.get("metrics", [])
    if isinstance(metrics, list):
        for metric in metrics:
            if not isinstance(metric, dict):
                continue

            value = metric.get("value")
            quote = clean_text(metric.get("quote", ""))

            if quote and quote not in source_text:
                issues.append(
                    f"Metric quote not found in source: "
                    f"{metric.get('name', 'unknown metric')}"
                )
                metric["quote"] = ""
                fixes.append(
                    f"Removed unsupported quote for "
                    f"{metric.get('name', 'unknown metric')}"
                )
                continue

            if value is not None and quote and not number_in_quote(
                value, quote
            ):
                issues.append(
                    f"Metric value {value!r} not found in quote for "
                    f"{metric.get('name', 'unknown metric')}"
                )
                metric["value"] = None
                fixes.append(
                    f"Cleared unverified value for "
                    f"{metric.get('name', 'unknown metric')}"
                )

    # Check guidance claims when present.
    guidance = result.get("guidance", [])
    if isinstance(guidance, list):
        for item in guidance:
            if not isinstance(item, dict):
                continue

            value = item.get("value")
            quote = clean_text(item.get("quote", ""))

            if quote and quote not in source_text:
                issues.append(
                    f"Guidance quote not found in source: "
                    f"{item.get('metric', item.get('name', 'unknown guidance'))}"
                )
                item["quote"] = ""
                fixes.append("Removed unsupported guidance quote")
                continue

            if value is not None and quote and not number_in_quote(
                value, quote
            ):
                issues.append(
                    f"Guidance value {value!r} not found in quote"
                )
                item["value"] = None
                fixes.append("Cleared unverified guidance value")

    return result, issues, fixes
