from agents.schemas import ExtractionResult, Metric
from agents.verify_source import check_against_source


def make_metric(name, value):
    return Metric(
        name=name,
        value=value,
        unit="USD_million",
        period="Q4 FY2026",
        source_quote=f"{name}: {value}",
    )


def make_result(*metrics):
    return ExtractionResult(
        company="Example Corp",
        period="Q4 FY2026",
        metrics=list(metrics),
    )


def test_revenue_value_must_be_near_revenue_label():
    result = make_result(make_metric("revenue", 18))
    source = "Share repurchases totaled 18 million dollars."

    checked, issues = check_against_source(result, source)

    assert not checked.metrics
    assert any("revenue" in issue.lower() for issue in issues)


def test_revenue_value_with_revenue_label_is_kept():
    result = make_result(make_metric("revenue", 18))
    source = "Revenue reached 18 million dollars."

    checked, _ = check_against_source(result, source)

    assert len(checked.metrics) == 1
    assert checked.metrics[0].value == 18


def test_net_income_value_must_be_near_net_income_label():
    result = make_result(make_metric("net_income", 25))
    source = "Operating expenses were 25 million dollars."

    checked, issues = check_against_source(result, source)

    assert not checked.metrics
    assert any("net_income" in issue.lower() for issue in issues)


def test_net_income_value_with_label_is_kept():
    result = make_result(make_metric("net_income", 25))
    source = "Net income was 25 million dollars."

    checked, _ = check_against_source(result, source)

    assert len(checked.metrics) == 1
    assert checked.metrics[0].value == 25
