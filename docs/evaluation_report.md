# Evaluation Report (draft, Day 21)

All numbers below were measured on the NVIDIA FY2026 10-K, the Q4 FY26 earnings call and a fictional Northwind Q3 FY26 call. Rows marked TBD are not measured yet.

## 1. Extraction accuracy (5 documents, answer keys)
- 28/28 headline values correct, 0 hallucinated values.
- Source quotes found in the document: 13 to 17 of 22 across runs (13/22 in the latest v9 run; PDF citations are the weakest).
- Latest v9 run (19 Oct), 22 non-null scored values: 10 came from Nemotron and 12 from the table-row and transcript fallback (earlier runs: about 16 and 6). Describe the system as a hybrid of LLM extraction, a code fallback and a verification layer; do not claim "all by Nemotron".
- Verification now runs on every extraction path (it was skipped before v9). It dropped a wrong model revenue value (30000) on the 10-K PDF, and also dropped one correct value on the 10-K text that the fallback then recovered.

## 2. Q&A (/chat) on a 9-question starter set (one document, 10-K)
| Run | Server image | Correct | Citations grounded in source |
|---|---|---|---|
| 1 | v7 | 7/9 | 7/7 |
| 2 | v8 | 8/9 | 13/13 |
| 3 | v8 | 9/9 | 13/13 |
| 4 | v9 | 9/9 | 13/13 |
| 5 | v9 | 9/9 | 11/11 |
- Repeat checks on v8: operating income 5/5 correct, diluted EPS 5/5 correct, unanswerable question abstained 3/3.
- On this 9-question set, no wrong figures were observed in v7 to v9 runs (the 20-question set in section 3 did produce wrong answers); all misses were false abstains (the strict number check abstains rather than guesses).

## 3. Q&A (/chat) on the 20-question set (hosted v10, 20 Oct)
The 20 questions (18 on the 10-K, 2 on the fictional Northwind call) were drafted by the team lead with AI assistance, and the answer keys were derived from the source documents (agents/eval/qa_full.json). One question (n2) was reworded after the first two runs because the original wording was wrong (two customers, not the largest); no other question was changed after seeing results.

| Run | Question set | Script score | Honest score (units checked) | Citations grounded |
|---|---|---|---|---|
| 1 | original | 14/20 | 13/20 | 16/16 |
| 2 | original | 14/20 | 13/20 | 17/17 |
| 3 | n2 reworded | 17/20 | not recorded | 24/24 |
| 4 | n2 reworded | 17/20 | 16/20 | 21/21 |

A further run was discarded because 9 questions hit HTTP 429 (rate limit) before being answered; it says nothing about answer quality.

- Stable passes in every run: stated figures (revenue, net income, operating income, diluted EPS, gross profit, prior-year revenue), operating expenses, the export-impact estimate on the Northwind call, and all 3 unanswerable questions (refused every time).
- Stable misses (false abstains, no wrong number given): derived margins (s11, s12, s13). EPS growth (s8) abstained in 3 of 4 runs.
- Wrong answers found: s14 gave "$85,441 billion" instead of million (the script counts it correct because it matches digits only); s10 once gave FY2025 revenue as cost of revenue with a grounded citation. Logged as Bugs 20 to 22 in docs/bug_list.md.
- Do not claim zero hallucinations for /chat. The zero-hallucination result applies to extraction only.

- TBD: accuracy on the 20-question set (waiting for the final set).

## 4. Risk and sentiment stability (hosted v6, call PDF, 6 repeat runs)
- Risk level "high" in 6/6 runs (7/8 across all runs; one earlier run gave "medium").
- 4 to 5 risks per run; competition, regulatory/export and supply chain risks found in all 6 runs.
- Tone score 0.75, hedging level and Q&A pushback identical in every run.

## 5. Model benchmark (Nebius Token Factory, 23 extraction values)
| Model | Result | Time |
|---|---|---|
| Nemotron 3 Nano 30B | 23/23 in 5/5 runs | 28-48 s |
| Nemotron 3 Super 120B | 23/23 in 4/4 runs | 29-34 s |
| Nemotron 3.5 Lightning | 23/23 in 1/4 runs | n/a |
| Qwen3-30B | 23/23 | 482 s |
| gpt-oss-120b | 19/23 (4 missing, 0 wrong) | n/a |
- Default model: Nemotron 3 Nano 30B, chosen for reliability (23/23 in 5/5 runs, 9/9 hosted chat eval twice). Super 120B is the benchmarked alternative (switch via NEBIUS_MODEL, no rebuild).
- Approx. cost per full benchmark run: Nano $0.005 to $0.007, Super about $0.023, Qwen3-30B about $0.014, gpt-oss-120b about $0.018.

## 6. Hallucination controls
- Every number in an answer must appear in its cited source sentences, otherwise the answer is replaced by "The document does not say."
- Citations are sentence IDs resolved by code, then checked against the document text.
- Unanswerable questions abstain (3/3 repeat runs, and again in both v9 runs).
- Extraction verification checks every value and quote against the source; wrong values are dropped, not shown.

## 7. API robustness (hosted v9)
- Hosted smoke test: 9/9 endpoint checks pass (health, documents, extract, metrics, analyze, chat with citations, trends, brief, compare).
- /chat returns structured errors on 6/6 invalid-input cases (unknown document, blank, empty and oversized message, unknown conversation, unknown conversation lookup).

## 8. Known limitations (state these in the README)
- The Q&A sets are small (9 and 20 questions, mostly on one NVIDIA document); results are indicative, not a benchmark. The 20 questions were drafted with AI assistance and checked against the sources.
- Plain years and period labels are not verified by the number check.
- The model sometimes returns badly formatted JSON; retries and a double-check before abstaining reduce but do not remove false abstains.
- PDF and text versions of the same document give slightly different hedging scores; hedging bands are provisional, tuned on 3 NVIDIA calls.
- The hosted demo runs on a free tier and may sleep or reset its data.
- /chat marks an answer as answered only when it has citations; an empty agent answer returns HTTP 502 since v10.
- Derived values (margins, growth rates) are often refused instead of computed (s11 to s13 failed in every run; s8 in 3 of 4 runs). This is a safe failure, not a wrong number.
- The number check confirms that a number exists in the document, not that it belongs to the asked line item or unit. Seen once: cost of revenue answered with FY2025 revenue (s10); and "$85,441 billion" instead of million (s14). See Bugs 20 and 21 in docs/bug_list.md.
- The zero-hallucination result applies to extraction, not to /chat.
- Automatic answer matching compares digits only, so unit errors need a manual check.
- The Q&A evaluation hits the server rate limit if questions are sent too fast; runs with HTTP 429 errors were discarded.
