"""Run: python3 scripts/brief_test.py  - checks the brief against the saved probe (no model calls)."""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.brief import build_brief
from agents.sentiment import _norm
from agents.verify import clean_text

probe = pathlib.Path("/tmp/brief_probe.json")
if not probe.exists():
    sys.exit("missing /tmp/brief_probe.json - re-run the probe command")
orch = json.loads(probe.read_text())
src = _norm(clean_text(pathlib.Path("data/sample/nvidia_Q4FY26_call.txt").read_text(encoding="utf-8", errors="replace")))
b = build_brief(orch)
md = b["markdown"]
fails = 0
def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name); fails += (not cond)

check("revenue shown as $68.0B", "$68.0B" in md)
check("period is Q4 2026", b["period"] == "Q4 2026")
check("guided gross margin 74.9% present", "74.9%" in md)
check("risk level and sentiment in headline", b["headline"]["risk_level"] == "high" and b["headline"]["overall_sentiment"] == "positive")
check("measured hedging 0.37 shown", "0.37" in md)
sev = [r["severity"] for r in b["risks"]]
check("1 to 5 risks, sorted by severity", 1 <= len(sev) <= 5 and sev == sorted(sev, reverse=True))
import re
check("no None/NaN leaks into the markdown", "None" not in md and not re.search(r"\bnan\b", md, re.I))
check("metric quotes found in the source (and there are some)", len(b["metrics"]) > 0 and all(_norm(m["source_quote"]) in src for m in b["metrics"]))
check("risk quotes found in the source (and there are some)", len(b["risks"]) > 0 and all(_norm(r["quote"]) in src for r in b["risks"]))
check("no duplicate guidance rows", len({(g["metric"], g["basis"], g["period"], g["display"]) for g in b["guidance"]}) == len(b["guidance"]))
empty = build_brief({"results": {}})
check("empty input does not crash, says not available", "Not available" in empty["markdown"])
check("brief is valid JSON", bool(json.dumps(b)))
print("\nALL PASSED" if not fails else f"\n{fails} FAILED")
sys.exit(fails)
