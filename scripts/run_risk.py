# Run: PYTHONPATH=. python3 scripts/run_risk.py [file1 file2 ...]
import sys, json, pathlib
from agents.risk import analyze_risk

DEFAULT = ["data/samples/transcript1.txt", "data/samples/transcript2.txt", "data/samples/cfo_q2fy27.txt"]
out_dir = pathlib.Path("docs/risk_runs"); out_dir.mkdir(exist_ok=True)
for path in sys.argv[1:] or DEFAULT:
    out = analyze_risk(open(path, errors="ignore").read())
    r = out["result"]
    print(f"\n== {path}")
    print(f"overall={r['overall_risk_level']} | risks kept: {out['quotes_kept']}/{out['quotes_total']} | retries: {out['retries']}")
    for x in r["risks"][:5]:
        print(f"  sev {x['severity']} [{x['category']}, {x['status']}] {x['title']}")
    for i in out["issues"]:
        print("  issue:", i)
    (out_dir / (pathlib.Path(path).stem + ".json")).write_text(json.dumps(out, indent=2))
