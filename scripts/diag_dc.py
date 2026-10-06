# scripts/diag_dc.py -- where do the chunks containing the real answer rank for the data center query?
from agents.retrieval import build_index, search

text = open("data/sample/nvidia_Q4FY26_10K.txt", encoding="utf-8").read()
vectors, meta = build_index(text, "nvidia_Q4FY26_10K")   # uses the cached index, no new embedding cost

# Phrases copied from the filing lines we just found
MARKERS = ["Data Center revenue for fiscal year 2026 was up 68%",
           "Revenue from Data Center networking grew 142%",
           "Data Center $ 193,737"]

ranked = search("How did data center revenue change?", vectors, meta, k=len(meta))  # rank all chunks
for marker in MARKERS:
    for rank, r in enumerate(ranked, start=1):
        if marker in " ".join(r["text"].split()):       # collapse whitespace before matching
            print(f"rank {rank:3d}  score {r['score']:.3f}  {r['chunk_id']}  <- {marker[:45]}")
            break
    else:
        print("NOT FOUND in any chunk:", marker)
