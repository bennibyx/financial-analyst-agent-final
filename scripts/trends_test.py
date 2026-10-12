"""Run: python3 scripts/trends_test.py  - checks the trend numbers against the known source figures."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.trends import build_trends

t = build_trends()
fails = 0
def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name); fails += (not cond)
def approx(a, b, tol=0.06):
    return a is not None and abs(a - b) <= tol

ser = {(s["metric"], s["basis"]): s["points"] for s in t["series"]}
rev, fcf = ser[("revenue", None)], ser[("free_cash_flow", None)]
check("revenue QoQ Q1 = +20.59%", approx(rev[1]["qoq_change"], 20.59))
check("revenue QoQ Q2 = +17.07%", approx(rev[2]["qoq_change"], 17.07))
check("Q4 revenue YoY stated = 73%", rev[0]["yoy_pct_stated"] == 73.0)
check("Q1 free cash flow is not_reported (a gap, not a guess)", fcf[1]["status"] == "not_reported" and fcf[1]["qoq_change"] is None)

pairs = t["guidance_track"]["pairs"]
rv = [r for p in pairs for r in p["compared"] if r["metric"] == "revenue"]
check("two revenue guidance comparisons", len(rv) == 2)
check("Q1 revenue beat = +5.13%", approx(rv[0]["diff"], 5.13) and rv[0]["verdict"] == "above")
check("Q2 revenue beat = +5.49%", approx(rv[1]["diff"], 5.49) and rv[1]["verdict"] == "above")
check("both beats are outside the +/-2% band", all(r["beyond_band"] for r in rv))
gm = [r for r in pairs[0]["compared"] if r["metric"] == "gross_margin"]
check("Q1 gross margin guidance in line (GAAP and non-GAAP)", len(gm) == 2 and all(r["verdict"] == "in_line" for r in gm))
check("full-year guidance skipped, never compared", any("full-year" in s["reason"] for s in pairs[1]["skipped"]))
check("every compared row has a period match", all(r["period_match"] for p in pairs for r in p["compared"]))
check("average revenue beat ~ 5.31%", approx(t["guidance_track"]["summary"]["revenue_avg_beat_pct"], 5.31, 0.1))

check("hedging trend is down", t["tone"]["direction"] == "less_hedging")

o = t["outlook"]
check("Q3 revenue guide 108B implies +12.5% QoQ", approx(o["revenue"]["implied_qoq_pct"], 12.5))
check("Q3 revenue range 105,840 to 110,160", o["revenue"]["range_musd"] == [105840, 110160])
check("Q3 gross margin implies -1.0 pt", approx(o["gross_margin"]["implied_change_pts"], -1.0))
check("output is valid JSON", bool(json.dumps(t)))
print("\nALL PASSED" if not fails else f"\n{fails} FAILED")
sys.exit(fails)
