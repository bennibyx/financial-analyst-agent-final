# Resume bullets (v9, measured numbers only)
Project: Autonomous Financial Analyst & Earnings Call Intelligence Agent | Nebius x NVIDIA Hackathon

- Built a multi-agent system (extraction, risk and sentiment, citation-based Q&A, plus an orchestrator) on NVIDIA Nemotron via Nebius Token Factory that turns 10-Ks and earnings calls into structured metrics, risks and tone scores.
- Reached 28/28 correct headline values with 0 hallucinated values on 5 NVIDIA documents by combining LLM extraction, a table-row fallback and a code verification layer that checks every value and quote against the source.
- Achieved 9/9 correct answers in two repeated hosted runs of a 9-question evaluation, with 24 of 24 checked citations found in the source text and unanswerable questions abstaining instead of guessing.
- Benchmarked 5 open models on Token Factory; chose Nemotron 3 Nano 30B for reliability (23/23 extraction values in 5/5 runs) and found Lightning dropped values in 3 of 4 runs.
- Found and fixed a bug where the verification step was silently skipped on every path, then deployed a containerized FastAPI service on Render, passing 9/9 hosted endpoint checks and 6/6 invalid-input error cases.

Limits: 9-question Q&A set, one document type (NVIDIA filings), about 12 of 22 extraction values came from the code fallback.
