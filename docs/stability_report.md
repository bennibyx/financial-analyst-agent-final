# Stability: repeated /analyze on the same document (hosted v6)

Document: NVIDIA Q4 FY26 earnings call (PDF). 6 repeat runs via scripts/stability_check.py.

| Measure | Result |
|---|---|
| Overall risk level | high in 6/6 runs (7/8 including two earlier hosted runs; one returned medium with 2 risks) |
| Risks per run | 4 to 5 |
| Categories present in all runs | competition, regulatory_export, supply_chain |
| Categories in some runs | execution (5/6), demand (3/6), macro (1/6) |
| Tone score | 0.75 in 6/6 |
| Hedging level / Q&A pushback | identical in 6/6 (hedging is measured in code, not by the model) |

Takeaway: core outputs are stable; marginal risks vary because the model proposes them and the quote check plus judge verify them.
