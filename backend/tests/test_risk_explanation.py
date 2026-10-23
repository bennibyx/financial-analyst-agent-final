from types import SimpleNamespace as NS
from agents.risk import verify_risks

SRC = ("We believe the pipeline is healthy, although supply of advanced packaging remains tight "
       "and could limit how much we ship. Export license rules for a major region continue to change. "
       "If restrictions tighten the impact could be $250 million of revenue.")

def risk(title, quote, expl, sev=4):
    return NS(title=title, quote=quote, explanation=expl, severity=sev, quantified=False)

def test_figure_not_in_quote_is_removed_and_severity_capped():
    r = NS(overall_risk_level="high", risks=[
        risk("Packaging", "supply of advanced packaging remains tight and could limit how much we ship",
             "Supply is tight and the CFO quantifies a $250 million revenue impact."),
        risk("Export rules", "Export license rules for a major region continue to change",
             "Rules are unpredictable, with a potential $250 million impact."),
    ])
    r, issues, kept, total = verify_risks(r, SRC)
    assert all("250" not in x.explanation for x in r.risks)
    assert all(x.quantified is False and x.severity == 3 for x in r.risks)
    assert r.overall_risk_level == "medium"
    assert any("not in the quote" in i for i in issues)

def test_figure_in_quote_is_kept():
    r = NS(overall_risk_level="high", risks=[
        risk("Revenue hit", "the impact could be $250 million of revenue",
             "The quote gives a $250 million revenue impact.")])
    r, issues, kept, total = verify_risks(r, SRC)
    assert r.risks[0].quantified is True
    assert r.risks[0].severity == 4
    assert "$250 million" in r.risks[0].explanation
