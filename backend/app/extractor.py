import re


def extract_financial_metrics(text: str) -> dict:
    """Extract common financial metrics and numeric values."""

    metrics = {}

    # Revenue amounts such as "$12.5 billion" or "12.5 million"
    revenue_matches = re.findall(
        r"\brevenue\b.{0,80}?\$?\s*([\d,]+(?:\.\d+)?)\s*"
        r"(million|billion|m|bn)?",
        text,
        re.IGNORECASE,
    )

    if revenue_matches:
        metrics["revenue"] = [
            {
                "value": float(value.replace(",", "")),
                "unit": unit or "",
            }
            for value, unit in revenue_matches
        ]

    # Revenue growth such as "revenue growth of 18%" or "revenue increased by 18 percent"
    growth_matches = re.findall(
        r"(?:revenue growth|sales growth|grew by|increased by)\s*"
        r"(?:of\s*)?([\d,.]+)\s*(%|percent)",
        text,
        re.IGNORECASE,
    )

    if growth_matches:
        metrics["revenue_growth"] = [
            {
                "value": float(value.replace(",", "")),
                "unit": "percent",
            }
            for value, _ in growth_matches
        ]

    # Operating margin such as "operating margin of 24.5%"
    margin_matches = re.findall(
        r"operating margins?(?:\s+(?:of|at|were|was))?\s*"
        r"([\d,.]+)\s*(%|percent)",
        text,
        re.IGNORECASE,
    )

    if margin_matches:
        metrics["operating_margin"] = [
            {
                "value": float(value.replace(",", "")),
                "unit": "percent",
            }
            for value, _ in margin_matches
        ]

    # EPS such as "EPS of $2.35"
    eps_matches = re.findall(
        r"(?:EPS|earnings per share)\s*(?:of|was|were)?\s*"
        r"\$?\s*([\d,.]+)",
        text,
        re.IGNORECASE,
    )

    if eps_matches:
        metrics["eps"] = [
            {
                "value": float(value.replace(",", "")),
                "unit": "USD",
            }
            for value in eps_matches
        ]

    return metrics