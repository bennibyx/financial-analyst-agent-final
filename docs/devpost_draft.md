**Repo:** https://github.com/bennibyx/financial-analyst-agent-final   **Demo:** https://financial-analyst-agent-v1.onrender.com   **Video:** (YouTube link)

## What it does
Upload an earnings-call transcript or an SEC filing (PDF, TXT or HTML). A team of AI agents extracts the key metrics with the exact source quote for every number, rates risks and management tone with evidence, answers questions with citations, compares quarters, and writes a one-click analyst brief.

## Why it is different: the model proposes, code verifies
Financial users cannot accept invented numbers. After every model call, code checks the output against the source:
- every number must appear in the document next to its label, or it is dropped;
- impossible values are fixed or dropped (for example, a percentage above 100);
- every quote must exist in the document, or it is rejected;
- if no risk can be verified, the rating is "unknown", never "low";
- hedging language is measured by counting phrases in code, not by asking the model.

## How we used NVIDIA and Nebius
All LLM calls go through Nebius Token Factory on NVIDIA Nemotron models. We benchmarked five open models on the same documents with the same answer keys. Nemotron 3 Nano 30B gave a perfect 23/23 in 5 of 5 runs; the larger Nemotron 3 Super was equally accurate (4 of 4 runs), so we kept Nano as our default. Token Factory is the only Nebius product we used; the demo is hosted on Render.

## Results (honest numbers)
- Extraction: 28/28 values correct on 5 test documents, 0 invented values (small set, prompts tuned on it; two of the five are the same 10-K as text and PDF; the earnings-call transcripts used in testing are not included in the public repo).
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

## Tool feedback (Nebius Token Factory and NVIDIA Nemotron)
What worked: one API let us swap between five models cheaply, and Nemotron 3 Nano 30B was fast and reliable enough to be our default. What was hard: rate limits. We hit 429 errors during evaluation runs and had to discard one run. Pricing was also hard to find, and one model had no price listed. Suggestions: document per-model rate limits, return retry-after hints, and show prices on each model's page.