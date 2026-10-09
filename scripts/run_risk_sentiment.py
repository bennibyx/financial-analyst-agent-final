# Run: PYTHONPATH=. python3 scripts/run_risk_sentiment.py [file1 file2 ...]
import sys, json, pathlib
from agents.risk_sentiment import analyze_risk_sentiment

DEFAULT = ["data/samples/transcript1.txt", "data/samples/transcript2.txt", "data/samples/cfo_q2fy27.txt"]
out_dir = pathlib.Path("docs/risk_sentiment_runs"); out_dir.mkdir(exist_ok=True)
for path in sys.argv[1:] or DEFAULT:
    out = analyze_risk_sentiment(open(path, errors="ignore").read())
    s, r = out["sentiment"], out["risk"]
    print(f"\n== {path} | schema {out['schema_version']}")
    print("sentiment:", f"{s['overall_tone']} {s['tone_score']}" if s else "FAILED", "| risk:", f"{r['overall_risk_level']}, {len(r['risks'])} risks" if r else "FAILED")
    for k, v in out["errors"].items():
        print(f"  ERROR in {k}: {v}")
    print("  issues:", len(out["issues"]))
    (out_dir / (pathlib.Path(path).stem + ".json")).write_text(json.dumps(out, indent=2))
