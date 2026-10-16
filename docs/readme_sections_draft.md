<!-- DRAFT: update numbers marked (TBD) after the /chat evaluation (Alekhya's 20 questions). -->

## How we use NVIDIA Nemotron and Nebius Token Factory
- All LLM calls go through Nebius Token Factory (OpenAI-compatible API). Default model: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B, with reasoning turned off for fast, structured JSON.
- We benchmarked 5 models on the same 4 documents (23 values): see docs/benchmark_report.md.

| Model | Perfect runs (23/23) | Time per run | Approx. cost per run |
|---|---|---|---|
| Nemotron 3 Nano 30B (chosen) | 5 of 5 | 28 to 48 s | $0.005 to $0.007 |
| Nemotron 3 Super 120B | 4 of 4 | 29 to 34 s | about $0.023 |
| Nemotron 3.5 Lightning | 1 of 4 | 29 to 62 s | n/a |
| Qwen3-30B Instruct | 1 of 1 | 482 s | about $0.014 |
| gpt-oss-120b | 0 of 1 (19/23) | 41 s | about $0.018 |

Why Nano: same accuracy as the larger Nemotron model at roughly one third to one fifth of the cost per run.
Honest limits: small test, prompts tuned on Nemotron Nano, one to five runs per model.

## Reliability and evaluation
We do not trust the model alone. Checks run in code after every model call:
1. Every extracted number must appear in the source text next to its label, or it is dropped.
2. Impossible values are fixed or dropped (for example, a percent above 100).
3. Every quote used as evidence must exist in the document; a second pass rejects quotes that do not support the claim.
4. Unsupported claims are downgraded; if no risk can be verified, the rating is "unknown", never "low".
5. Hedging language is measured by counting phrases in code, not by asking the model.

| Test | Result |
|---|---|
| Extraction accuracy, 5 documents, 28 values | 28/28 correct, 0 hallucinated, 0 wrong, 0 missing |
| Quotes found verbatim in the source | 17 of 22 (weakest on PDFs) |
| Repeat runs on the same call (risk rating) | identical "high" in 6 of 6 runs; tone and hedging identical |
| Hosted smoke test (9 endpoints) | 9/9 passing |
| Q&A accuracy and citation rate (20 questions) | (TBD) |

Limits: the 5 documents are all from NVIDIA and were used while tuning the prompts, so scores are optimistic. Details: docs/verification_report.md, docs/stability_report.md.
