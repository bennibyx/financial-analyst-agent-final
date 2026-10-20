
# Autonomous Financial Analyst & Earnings Call Intelligence Agent

**Repo:** https://github.com/bennibyx/financial-analyst-agent-final   **Demo:** https://financial-analyst-agent-v1.onrender.com   **Video:** (YouTube link)

## What it does
Upload an earnings-call transcript or an SEC filing (PDF, TXT or HTML). A team of AI agents extracts the key metrics with the exact source quote for every number, rates risks and management tone with evidence, answers questions with citations, compares quarters, and writes a one-click analyst brief.

## Why it is different: the model proposes, code verifies
Financial users cannot accept invented numbers. After every model call, code checks the output against the source:
- every number must appear in the document next to its label, or it is dropped;
- impossible values are fixed or dropped (for example, a percentage above 100);
- every quote must exist in the document, and a second pass rejects quotes that do not support the claim;
- if no risk can be verified, the rating is "unknown", never "low";
- hedging language is measured by counting phrases in code, not by asking the model.

## How we used NVIDIA and Nebius
All LLM calls go through Nebius Token Factory on NVIDIA Nemotron models. We benchmarked five open models on the same documents with the same answer keys. Nemotron 3 Nano 30B gave a perfect 23/23 in 5 of 5 runs at about $0.005 to $0.007 per run; the larger Nemotron 3 Super was equally accurate at roughly 3 to 5 times the cost, so Nano is our default. Token Factory is the only Nebius product we used; the demo is hosted on Render.

## Results (honest numbers)
- Extraction: 28/28 values correct on 5 NVIDIA documents, 0 invented values (small set, prompts tuned on it; some of the five are call transcripts we cannot redistribute, so the public repo includes only the filings).
- Stability: the same risk rating in 6 of 6 repeat runs on a call transcript.
- Hosted API: 9/9 endpoint checks pass.
- Q&A: 20 questions we wrote ourselves (18 on an NVIDIA 10-K, 2 on a fictional demo call). On the hosted API, 16/20 were correct by strict grading and 17/20 by script; all cited quotes were found in the source (24/24 and 21/21 across two runs) and 3/3 unanswerable questions were correctly declined. Weak spots: derived margins and EPS growth.

## How we built it
FastAPI backend with document parsing, a database and a vector store; Python agents with Pydantic-validated JSON output; a Streamlit dashboard; Docker image deployed to a public URL. Three people: agents and evaluation, backend and deployment, dashboard and demo.

## Challenges
- PDF text artifacts broke exact quote matching; we made the checks tolerant of them without letting invented quotes through.
- Automated tests on the hosted API caught a gross profit amount stored as a percentage; we added a plausibility guard and a regression test.
- Different models need different settings; we benchmarked them instead of assuming.

## What we learned
Measuring beats guessing: repeat runs, answer keys and sanity checks found bugs that single demos hid.

## What is next
More companies and filing types, a larger and independent evaluation set, deeper cross-quarter analysis.
