# Tool Feedback Log (draft for Devpost)

| Date | Tool | What worked | Issue / Suggestion |
|---|---|---|---|
| 2026-10-16 | Nebius Token Factory: Nemotron 3 Nano 30B | 23/23 extraction values in 5/5 runs, 28-48 s | With thinking off it sometimes returns JSON with wrong keys or no JSON (about 1 in 18 Q&A calls locally); we added schema validation, retries and a double-check before abstaining |
| 2026-10-16 | Nebius Token Factory: Nemotron 3 Super 120B | 23/23 in 4/4 runs, 29-34 s, fewest calls and tokens | TODO: add price per 1M tokens after checking the console, then decide default model |
| 2026-10-16 | Nebius Token Factory: Nemotron 3.5 Lightning | Fast | 23/23 in only 1 of 4 runs (missed a value in 3 runs), so not reliable for structured extraction |
| 2026-10-16 | Nebius Token Factory: other open models | Qwen3-30B got 23/23; gpt-oss-120b got 19/23 with 0 wrong values | Qwen3-30B took 482 s, too slow for interactive use |
| 2026-10-17 | Nebius Token Factory: rate limits and docs | TODO | TODO: write one real thing you hit (rate limits, model names, latency spikes) |
| 2026-10-12 | Nebius AI Cloud | TODO | TODO: you chose a fallback host because you were unsure about console access; say exactly what blocked you |
| 2026-10-19 | Nebius Token Factory: Nemotron 3 Nano 30B (hosted app default) | Hosted chat eval 9/9 correct in 2 runs (citations grounded 13/13 and 11/11); extraction eval 28/28 values, 0 hallucinated | On dense 10-K text many chunks returned all-null metrics (13 of 22 values came from our table and transcript fallbacks in the latest run), so we added a verification layer and a table-row parser; a built-in structured-output or JSON-schema mode would reduce this |
