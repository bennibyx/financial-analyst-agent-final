# Run: python scripts/test_percent_guard.py   (Bug 12: percent metric above 100)
import sys; sys.path.insert(0, ".")
from types import SimpleNamespace as N
from agents.verify_source import check_against_source

text = "Revenue $ 215,938 $ 130,497\nGross profit 153,463 97,858\n"
def metrics(with_revenue=True):
    ms = [N(name="gross_margin", value=153463.0, unit="percent", period="FY2026", basis=None, source_quote="Gross profit 153,463")]
    if with_revenue:
        ms.insert(0, N(name="revenue", value=215938.0, unit="USD_million", period="FY2026", basis=None, source_quote="Revenue 215,938"))
    return N(metrics=ms)

res, issues = check_against_source(metrics(True), text)
gm = next(m for m in res.metrics if m.name == "gross_margin")
assert gm.value == 71.1, gm.value                 # 153463 / 215938 = 71.1 %

res, issues = check_against_source(metrics(False), text)
assert not any(m.name == "gross_margin" for m in res.metrics)   # no revenue -> dropped, never shown as 153,463 %
print("PASS percent guard (2/2)")
