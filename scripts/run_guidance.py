# Run: PYTHONPATH=. python3 scripts/run_guidance.py
import json, glob, os, pathlib
from agents.guidance_compare import compare_guidance

def newest_good_run():
    for f in sorted(glob.glob("docs/eval_runs/*.json"), key=os.path.getmtime, reverse=True):
        d = json.load(open(f))
        if all(isinstance(d.get(k), dict) and "raw_metrics" in d[k] for k in ("doc1", "doc2", "doc3")):
            return f, d
    raise SystemExit("no complete eval run found")

f, d = newest_good_run()
print("using saved run:", f[-11:-5])
ext = lambda x: {"metrics": x["raw_metrics"], "guidance": x["raw_guidance"]}
results = {}
for a, b in [("doc1", "doc2"), ("doc2", "doc3")]:     # the call that guided -> the call that reported
    rows = compare_guidance(ext(d[a]), ext(d[b]))
    results[f"{a}_to_{b}"] = rows
    print(f"\n== guidance in {a} vs reported in {b}")
    for r in rows:
        if r["verdict"] == "no_match":
            print(f"  {r['metric']}: no matching reported value")
            continue
        warn = "" if r["period_match"] else f"   <-- PERIOD CHECK: guided '{r['guided_period']}' vs reported '{r['actual_period']}'"
        print(f"  {r['metric']} ({r['basis'] or 'no basis'}): guided {r['guided']} {r['guided_unit']} -> reported {r['actual']} {r['actual_unit']} | {r['diff']:+}{r['diff_unit']} {r['verdict']}{warn}")
out = pathlib.Path("docs/guidance_runs"); out.mkdir(exist_ok=True)
(out / "guidance_vs_actual.json").write_text(json.dumps(results, indent=2))
