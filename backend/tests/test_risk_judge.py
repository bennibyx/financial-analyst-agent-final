from types import SimpleNamespace

from agents.risk_judge import judge_support


def make_risk(title, quote):
    return SimpleNamespace(title=title, quote=quote)


def test_judge_keeps_supported_supply_chain_risk(monkeypatch):
    risk = make_risk(
        "Supplier shortages may delay deliveries",
        "supplier shortages may delay product deliveries next quarter",
    )
    result = SimpleNamespace(risks=[risk])

    def fake_ask_json(system, items, schema):
        return (
            SimpleNamespace(
                verdicts=[
                    SimpleNamespace(index=0, supports=True, harm=True)
                ]
            ),
            0,
        )

    monkeypatch.setattr("agents.risk_judge.ask_json", fake_ask_json)

    updated, issues = judge_support(result)

    assert len(updated.risks) == 1
    assert updated.risks[0].title == "Supplier shortages may delay deliveries"
    assert issues == []


def test_judge_rejects_unsupported_risk(monkeypatch):
    risk = make_risk(
        "Supplier shortages may delay deliveries",
        "revenue increased 18% this quarter",
    )
    result = SimpleNamespace(risks=[risk])

    def fake_ask_json(system, items, schema):
        return (
            SimpleNamespace(
                verdicts=[
                    SimpleNamespace(index=0, supports=False, harm=False)
                ]
            ),
            0,
        )

    monkeypatch.setattr("agents.risk_judge.ask_json", fake_ask_json)

    updated, issues = judge_support(result)

    assert updated.risks == []
    assert len(issues) == 1
    assert "judge rejected" in issues[0]


def test_judge_handles_no_risks():
    result = SimpleNamespace(risks=[])

    updated, issues = judge_support(result)

    assert updated.risks == []
    assert issues == []


def test_judge_keeps_explicit_delivery_delay_risk(monkeypatch):
    risk = make_risk(
        "Supplier shortages may delay product deliveries",
        "supplier shortages may delay product deliveries next quarter",
    )
    result = SimpleNamespace(risks=[risk])

    def fake_ask_json(system, items, schema):
        assert "Supplier shortages may delay product deliveries" in items
        assert (
            "supplier shortages may delay product deliveries next quarter"
            in items
        )
        return (
            SimpleNamespace(
                verdicts=[
                    SimpleNamespace(index=0, supports=True, harm=True)
                ]
            ),
            0,
        )

    monkeypatch.setattr("agents.risk_judge.ask_json", fake_ask_json)

    updated, issues = judge_support(result)

    assert len(updated.risks) == 1
    assert updated.risks[0].quote == (
        "supplier shortages may delay product deliveries next quarter"
    )
    assert issues == []
