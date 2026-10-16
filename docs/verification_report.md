# Verification Layer v1: how we limit hallucination

## Checks in the pipeline (code, not model)
1. Metric value must appear in the source text next to its label (label-aware); otherwise dropped.
2. Unit rescue: millions/billions mix-ups are corrected only when the corrected number is found in the source.
3. Plausibility guard: a percent above 100 is fixed from amount/revenue or dropped (Bug 12).
4. Risk quotes must exist in the transcript (letters+digits match, tolerant of PDF artifacts); a second judge pass rejects quotes that do not support the risk.
5. Unsupported claims are downgraded (e.g. Q&A pushback becomes "none" if no analyst question is quoted); unverified risks give "unknown", never "low".
6. Hedging is measured in code (phrase density per 1,000 words), not by the model.
7. Table-row fallbacks supply values the model misses (all 4 of 5 values on the 10-K PDF).

## Extraction accuracy (scripts/eval_extraction.py, run 2026-10-16)
| Documents | Values correct | Hallucinated | Wrong | Missing |
|---|---|---|---|---|
| 3 transcripts/CFO commentary + 10-K (txt) + 10-K (PDF) | 28/28 | 0 | 0 | 0 |

Quotes found verbatim in source: 17/22 (about 77%). Weakest on the PDF, where text artifacts break exact matching.
Run file: docs/eval_runs/extraction_20261016_093315.json

## Stability (docs/stability_report.md)
Overall risk level identical in 6/6 repeat runs; tone and hedging identical.

## Limits (be honest)
- Small set: 5 documents, 28 values, all from NVIDIA. Prompts were tuned on these documents, so the scores are optimistic.
- The eval does not yet cover /chat answers (waiting for the 20-question set).
- PDF citations are weaker than TXT; values are right, quotes are sometimes not verbatim.
- Bug 12 (percent field holding an amount) is covered by scripts/test_percent_guard.py and the hosted smoke test sanity check, not by this eval.
