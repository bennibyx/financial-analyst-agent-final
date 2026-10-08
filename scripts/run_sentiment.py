# Run: PYTHONPATH=. python3 scripts/run_sentiment.py [file1 file2 ...]
import sys, json, pathlib
from agents.sentiment import analyze_sentiment

DEFAULT = ["data/samples/transcript1.txt", "data/samples/transcript2.txt", "data/samples/cfo_q2fy27.txt"]
out_dir = pathlib.Path("docs/sentiment_runs"); out_dir.mkdir(exist_ok=True)
for path in sys.argv[1:] or DEFAULT:
    out = analyze_sentiment(open(path, errors="ignore").read())
    r = out["result"]
    print(f"\n== {path}")
    print(f"tone={r['overall_tone']} score={r['tone_score']} | prepared={r['prepared_remarks_score']} qa={r['qa_score']} | hedging={r['hedging_level']}")
    print(f"quotes grounded: {out['quotes_kept']}/{out['quotes_total']} | pushback items: {len(r['analyst_pushback'])} | retries: {out['retries']}")
    for p in r["analyst_pushback"][:2]:
        print("  pushback:", p["topic"], "| evasive:", p["evasive"])
    for i in out["issues"]:
        print("  issue:", i)
    (out_dir / (pathlib.Path(path).stem + ".json")).write_text(json.dumps(out, indent=2))
