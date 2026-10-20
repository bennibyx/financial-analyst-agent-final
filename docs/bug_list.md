# Day 17 Bug List (live test on Render, 2026-10-14)

| # | Bug | Severity | Owner |
|---|-----|----------|-------|
| 1 | 10-K: top-level period "Q4 2026" vs metrics "Fiscal Year 2026" | Medium | Bhavana |
| 2 | basis and yoy_change_pct null on 10-K and call metrics, even when the source states the change | Medium | Bhavana |
| 3 | Q4 FY26 call PDF: all 5 risk quotes dropped (quotes truncated), risks empty | High | Bhavana |
| 4 | PDF text artifacts ("|", "r amp") in evidence quotes | Medium | Bhavana |
| 5 | Empty risks reports "low" instead of "unknown" | High | Bhavana |
| 6 | Validation error says only "Field required" (no field name) | Low | Sandeep |
| 7 | Chat guidance answer omits gross margin guidance | Medium | Bhavana |
| 8 | Brief lacks net income, EPS, operating income, FCF (CFO commentary not wired in) | Medium | Bhavana |
| 9 | Render free tier sleeps and wipes data on restart | High | Sandeep + Bhavana (redeploy access) |
| 10 | Repo not public: FactSet transcripts in data/sample | High | Sandeep/Alekhya |

## Passing
/health, /upload (3 docs), /extract (10-K), /analyze job (call), /chat with correct citation, /brief (Q2 FY27 call)

## Fixed (2026-10-15)
- Bug 3: risk quote check now ignores PDF artifacts (agents/risk.py `_squash`); PDF returns 4 verified risks (scripts/check_pdf_risks.py)
- Bug 5: empty or unverified risks now give "unknown" instead of "low" (schema 1.2)
- Bug 11: NOT A BUG. Final hedging_level is measured from phrase density in code (analyze_sentiment); the model-side downgrade is overwritten.
- Bug 12 (High, Bhavana): 10-K gross_margin stored as 153463.0 "percent" (gross profit in USD million; should be ~71.1%). Found by hosted_smoke.py sanity check.
- Bug 13 (Medium, Bhavana): /chat answers "The document does not say" for diluted EPS FY2026 although it is in the 10-K (4.90). Safe failure, but a miss. Likely retrieval or the number check.
- Bug 14 (Medium, Bhavana): /chat answer for FY2025 revenue adds "up 65%" (that is FY2026 growth; FY2025 grew about 114%). Number correct, extra claim wrong. Check how growth percentages are attached to a period.
- To investigate: only 1 of 7 /chat citations matched the document text in scripts/eval_chat.py. Look at one raw /chat response first (may be a script limit).

## Found in the 20-question chat evaluation (2026-10-20)
- Bug 20 (Medium, Bhavana): /chat gives wrong units. s14 answered "Revenue increased by $85,441 billion" (should be million). The eval script matches digits only, so it scored this CORRECT. Honest score is 16/20 in v2 run 2 (script says 17/20).
- Bug 21 (High, Bhavana): /chat gave a confident wrong answer with a grounded citation. s10 answered "Cost of revenue for fiscal year 2026 was $130,497 million" (that is FY2025 revenue). Seen in 1 of 2 v1 runs. The number check only confirms a number exists in the document, not that it belongs to the asked line item.
- Bug 22 (Medium, Bhavana): derived and growth questions are unreliable. s11, s12, s13 (gross margin %, operating margin %, net margin %) abstain in every run, and s8 (EPS growth) abstained in 3 of 4 runs. Safe failure (no wrong number), but a miss. Reported as a known limitation, not fixed before the Oct 21 freeze.
