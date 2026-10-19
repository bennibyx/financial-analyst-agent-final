<!-- DRAFT: Q&A numbers come from a 9-question set; update them if a larger set is evaluated. -->

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
| Quotes found verbatim in the source | 13 to 17 of 22 across runs (weakest on PDFs) |
| Where the 22 extracted values come from (latest run) | 10 from Nemotron, 12 from the table and transcript fallback (a hybrid system) |
| Repeat runs on the same call (risk rating) | identical "high" in 6 of 6 runs; tone and hedging identical |
| Hosted smoke test (9 endpoints) | 9/9 passing |
| Hosted Q&A, 9-question starter set on the 10-K, 2 runs | 9/9 correct in both runs; 13/13 and 11/11 checked citations found in the source; the unanswerable question abstained |
| Invalid-input requests to /chat (6 cases) | 6/6 return structured errors |

Limits: the 5 documents are all from NVIDIA and were used while tuning the prompts, so scores are optimistic. The Q&A set has only 9 questions on one document. Details: docs/verification_report.md, docs/stability_report.md.
