# Prints every non-correct row from the latest eval run, plus the raw rows the agent returned.
import json, glob
f = sorted(glob.glob("docs/eval_runs/extraction_*.json"))[-1]
print(f)
MAP = {"eps_diluted": "eps"}
for doc, d in json.load(open(f)).items():
    if "crashed" in d:
        print("  ", doc, "CRASHED:", d["crashed"][:120]); continue
    for r in d["rows"]:
        if r["status"] in ("CORRECT", "OK_NULL", "NOT_IN_SCHEMA"):
            continue
        print("  ", doc, r["metric"], r["status"], "truth=", r["truth"])
        for m in d.get("raw_metrics", []):
            if m["name"] == MAP.get(r["metric"], r["metric"]):
                print("       raw:", m["value"], m["unit"], m["basis"], "|", (m["source_quote"] or "")[:70])
