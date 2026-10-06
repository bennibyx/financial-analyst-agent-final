# scripts/day5_retrieval.py -- test retrieval on the NVIDIA 10-K with 3 questions
import sys
from agents.retrieval import build_index, search

path = sys.argv[1] if len(sys.argv) > 1 else "data/sample/nvidia_Q4FY26_10K.txt"
text = open(path, encoding="utf-8").read()
vectors, meta = build_index(text, "nvidia_Q4FY26_10K")

QUERIES = ["What are the supply chain risks?",
           "How did data center revenue change?",
           "What are the export restrictions?"]
for q in QUERIES:
    print("\n=== " + q)
    for r in search(q, vectors, meta, k=3):
        print(f"[{r['score']:.3f}] {r['chunk_id']} ({r['section']})")
        print("   ", r["text"][:200].replace("\n", " "))
