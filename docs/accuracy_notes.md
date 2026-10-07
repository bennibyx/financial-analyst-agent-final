# Extraction Agent: accuracy notes (Day 7)

## Setup
- 3 documents, all NVIDIA: Q4 FY26 call, Q1 FY27 call, Q2 FY27 CFO commentary (tables).
- Hand-made answer keys in agents/eval/ground_truth/; scorer: scripts/eval_extraction.py.
- 15 items scored per run (6 metrics x 3 docs, minus operating_income, which is not in the schema).
- 6 of the 15 items are "not stated, must be null" checks.

## Results
| Version | Runs | Accuracy | Invented values |
|---|---|---|---|
| Baseline (original verifier) | 3 | 80%, 93%, 93% | 0 |
| v5 + verifier fix | 15 | avg ~96.5% (87-100%) | 0 |
| v6 prompt (experiment) | 8 | avg ~77% (60-100%) | 0 |

## Findings
1. Verifier bug: label check required number and label on one line; PDF table text splits them. Fixed by checking 2 lines above (agents/verify_source.py). Fixed against doc3 only; needs testing on other filings.
2. Intermittent failures at temperature 0: 4 of 15 v5 runs lost 2 items (model returned null). One early run crashed on invalid JSON (3 identical retries).
3. Prompt v6 (added "where to look" and "change pct" rules) regressed: model returned null for values it had quoted. Two rules changed at once, so the cause is unknown. Kept as docs/extraction_prompt_v6_REGRESSED.py.
4. Table quotes (doc3) are rebuilt by the model, not copied, so evidence is not verbatim. Needs cleaner table parsing upstream.
5. operating_income is not in the schema, so doc3's value cannot be extracted.

## Limits
- Same company only; small sample; prompt was tuned on transcripts like doc1/doc2.
- Accuracy here is value-only; quote verbatim check is separate (QUOTES FOUND IN SOURCE).

## Next
- Test one rule change at a time, 8+ runs each.
- Add documents from other companies.
- Ask Sandeep for table-aware parsing; decide on operating_income with Sandeep and Alekhya.
