# Run: python scripts/test_risk_verify.py
import sys; sys.path.insert(0, ".")
from agents.risk import RiskResult, RiskItem, verify_risks

src = "We expect supply constraints to impact the r amp of Blackwell | and lower revenue by $2.5 billion in the quarter."
def item(q):
    return RiskItem(category="supply_chain", title="t", severity=4, status="current",
                    quantified=True, quote=q, explanation="e")

r = RiskResult(overall_risk_level="low", risks=[
    item("supply constraints to impact the ramp of Blackwell and lower revenue by $2.5 billion..."),  # real, PDF-damaged
    item("Management warned that new tariffs would badly hurt gross margins next year"),             # invented
])
r, issues, kept, total = verify_risks(r, src)
assert total == 2 and kept == 1, (kept, total, issues)
print("PASS risk quote verification (PDF artifacts accepted, hallucination rejected)")
