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
