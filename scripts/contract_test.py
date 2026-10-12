"""Run: python3 scripts/contract_test.py  - checks every agent honours the contract."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents import service as s

DOC = pathlib.Path("data/sample/nvidia_Q4FY26_10K.txt").read_text()
fails = 0
def check(name, cond):
    global fails
    print(("PASS " if cond else "FAIL ") + name); fails += (not cond)

runs = {
    "extract":  s.extract_document(DOC),
    "analyze":  s.analyze_document(DOC),
    "ask":      s.ask_document("What was data center revenue?", DOC),
    "pipeline": s.run_pipeline(DOC, question="What are the main risks?"),
}
for name, env in runs.items():
    check(f"{name}: ok + data present", env.ok and bool(env.data))
    check(f"{name}: latency recorded", env.meta.latency_ms > 0)
    if not env.ok:
        print("   ->", env.error)

check("same text -> same doc_id", runs["extract"].meta.doc_id == runs["ask"].meta.doc_id)
check("empty text -> BAD_INPUT", s.extract_document("").error.code == "BAD_INPUT")
check("empty question -> BAD_INPUT", s.ask_document("", DOC).error.code == "BAD_INPUT")
print("\nALL PASSED" if not fails else f"\n{fails} FAILED")
sys.exit(fails)
