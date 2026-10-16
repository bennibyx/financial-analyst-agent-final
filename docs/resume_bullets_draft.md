# Resume bullets (DRAFT: update numbers after the Q&A evaluation, keep only what is true on the final day)
- Built a multi-agent financial analyst (extraction, risk and sentiment, citation-backed Q&A, orchestrator) on NVIDIA Nemotron via Nebius Token Factory; FastAPI backend shipped as a Docker image with a hosted demo.
- Designed a code-side verification layer (source grounding, plausibility guards, quote checks) that gave 28/28 correct values and 0 hallucinated values on a 5-document earnings and SEC-filing test, with the same risk rating in 6 of 6 repeat runs.
- Benchmarked 5 open models on Token Factory; chose Nemotron 3 Nano, matching the larger Nemotron model's accuracy at about 3 to 5 times lower cost per run.
- Found and fixed a data bug through automated hosted-API smoke tests (a gross profit amount stored as a percentage), and reached 9/9 passing endpoint checks.
