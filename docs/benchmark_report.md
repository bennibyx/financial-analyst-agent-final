# Model benchmark (Nebius Token Factory), 2026-10-16

Task: Extraction Agent on 4 documents with answer keys (2 transcripts, 1 CFO commentary, 1 10-K text), 23 values.
Script: scripts/benchmark_models.py. Raw runs: docs/benchmark_runs/.

| Model | Runs | Runs with 23/23 | Time per run (s) | Model calls | Tokens in / out (k) |
|---|---|---|---|---|---|
| nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B (current) | 5 | 5 of 5 | 28 to 48 | 7 to 9 | 51 to 82 / 6.5 to 9 |
| nvidia/nemotron-3-super-120b-a12b | 4 | 4 of 4 | 29 to 34 | 7 | 51 / 7.5 to 8.2 |
| nvidia/Nemotron-3_5-Lightning | 4 | 1 of 4 (22/23 in the other 3) | 29 to 62 | 9 | 85 / 7.8 to 8.1 |
| Qwen/Qwen3-30B-A3B-Instruct-2507 | 1 | 1 of 1 | 482 | 15 | 88 / 18.8 |
| openai/gpt-oss-120b | 1 | 0 of 1 (19/23, 4 missing) | 41 | 8 | 50 / 16.8 |

Across all runs: 0 hallucinated values and 0 wrong values. Errors were always missing values, because unverified values are dropped.

## Findings
- All three NVIDIA models are accurate on this set. Super was the most consistent and used the fewest tokens; Nano was equally accurate but with more varied speed; Lightning sometimes missed a value.
- Qwen3-30B was accurate but about 12 times slower (more retries, double the output tokens).
- gpt-oss-120b missed 4 values and wrote about twice as many output tokens.
- Decision: Nano stays the default for now. Super is the alternative if its price per token is acceptable (to be checked; token counts are recorded, prices are not).

## Limits (read before quoting numbers)
- Small test: 23 values, 4 documents, all NVIDIA, 1 to 5 runs per model. Prompts were tuned on Nemotron Nano, so this favours the NVIDIA models.
- The thinking-mode setting is only disabled for NVIDIA models; the other models ran with their own defaults, so setups were not identical.
- Timings vary with API load. Treat gaps under about 10 s as noise.

## Cost per benchmark run (4 documents, 23 values)
List prices per 1M tokens (input / output) on Nebius Token Factory as of 2026-10-09, taken from third-party price trackers (modelcompare.dev, amcompute.com): verify against Nebius's own pricing page before quoting.

| Model | Price in / out ($/M) | Cost per run |
|---|---|---|
| nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B (current) | 0.06 / 0.24 | about $0.005 to $0.007 |
| nvidia/nemotron-3-super-120b-a12b | 0.30 / 0.90 | about $0.023 |
| Qwen/Qwen3-30B-A3B-Instruct-2507 | 0.10 / 0.30 | about $0.014 |
| openai/gpt-oss-120b | 0.15 / 0.60 | about $0.018 |
| nvidia/Nemotron-3_5-Lightning | price not found | n/a |

Decision: Nano stays the default. It scored 23/23 in 5 of 5 runs at about one third to one fifth of Super's cost per run; Super was equally accurate (4 of 4 runs) with no clear speed advantage.
Costs are computed from the token counts in docs/benchmark_runs and ignore any free credits.
