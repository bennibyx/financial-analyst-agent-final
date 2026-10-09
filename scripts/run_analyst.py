# Run: PYTHONPATH=. python3 scripts/run_analyst.py            (built-in test questions)
#      PYTHONPATH=. python3 scripts/run_analyst.py "your question" data/samples/transcript1.txt
import sys, json, pathlib
from agents.analyst import answer_question

TESTS = [
    ("doc1", "data/samples/transcript1.txt", "What was total revenue and how much did it grow year over year?"),
    ("doc1", "data/samples/transcript1.txt", "What is the revenue outlook for next quarter?"),
    ("doc1", "data/samples/transcript1.txt", "What was the company's total number of employees?"),    # should be NOT FOUND
    ("doc2", "data/samples/transcript2.txt", "What is guided for gross margin next quarter?"),
    ("doc3", "data/samples/cfo_q2fy27.txt", "What was net income for the quarter?"),
]
if len(sys.argv) >= 3:
    TESTS = [("custom", sys.argv[2], sys.argv[1])]
out_dir = pathlib.Path("docs/analyst_runs"); out_dir.mkdir(exist_ok=True)
log = []
for doc_id, path, q in TESTS:
    out = answer_question(q, open(path, errors="ignore").read(), doc_id)
    r = out["result"]
    print(f"\nQ ({doc_id}): {q}")
    print("A:", r["answer"])
    for c in r["citations"]:
        print("   cite:", c["quote"][:140])
    print("   retrieved:", [(h["chunk_id"], h["score"]) for h in out["retrieved"][:3]], "| retries:", out["retries"])
    for i in out["issues"]:
        print("   issue:", i)
    log.append({"doc": doc_id, "question": q, **out})
(out_dir / "latest.json").write_text(json.dumps(log, indent=2))
