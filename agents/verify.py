
import re


def clean_text(text):
    """Normalize text before checking extracted financial claims."""
    if text is None:
        return ""
    return str(text).strip()


def number_in_quote(value, quote):
    """Verify numbers with decimal and billion/million equivalence."""
    if value is None:
        return True

    quote = clean_text(quote)

    try:
        target = float(value)
    except (TypeError, ValueError):
        return False

    pattern = r"(?<![\d,])[-+]?\d[\d,]*(?:\.\d+)?(?!\d)"

    for match in re.finditer(pattern, quote):
        try:
            found = float(match.group(0).replace(",", ""))
        except ValueError:
            continue

        if any(abs(found - equivalent) < 0.000001
               for equivalent in (target, target / 1000, target * 1000)):
            return True

    return False

def _verify_dict(result, text):
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
            quote = clean_text(metric.get("source_quote", ""))

            if quote and quote not in source_text:
                issues.append(
                    f"Metric quote not found in source: "
                    f"{metric.get('name', 'unknown metric')}"
                )
                metric["source_quote"] = ""
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
            quote = clean_text(item.get("source_quote", ""))

            if quote and quote not in source_text:
                issues.append(
                    f"Guidance quote not found in source: "
                    f"{item.get('metric', item.get('name', 'unknown guidance'))}"
                )
                item["source_quote"] = ""
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


def verify(result, text):
    """Accepts a dict or a schema object (the agents pass objects); runs the dict checks either way."""
    if hasattr(result, "model_dump"):
        data, issues, fixes = _verify_dict(result.model_dump(), text)
        return type(result).model_validate(data), issues, fixes
    return _verify_dict(result, text)
