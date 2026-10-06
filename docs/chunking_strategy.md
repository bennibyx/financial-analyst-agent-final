# Chunking Strategy (Day 4)

## Decision
Section-aware chunking for SEC filings, with a fixed-size fallback.

## Rules
1. Split the filing at Item headings: Item 1A (Risk Factors), Item 7 or 2 (MD&A), Item 8 or 1 (Financial Statements).
2. A heading must START a line and must not end in a page number. This skips cross-references inside sentences and table-of-contents lines.
3. Each section is cut into chunks of at most 4,000 characters with 400 characters of overlap.
4. pypdf output has almost no blank lines, so any oversized block is split into single lines first.
5. Markdown tables (lines starting with `|`) are never split. Currently inactive because pypdf produces no markdown tables.
6. If no headings are found, the whole text is chunked with the same size rules (fallback).
7. Every chunk carries `chunk_id`, `doc_id` and `section`, which gives free citation metadata for the Q&A agent.

## Result on NVIDIA Q4 FY26 10-K
93 pages, 358,441 characters, 103 chunks, all under 4,000 characters. Sections: other, risk_factors, mdna, financial_statements. Item 1 (Business) is not in the pattern list, so it lands in `other`.

## Tradeoff
- Fixed-size chunking: simplest, but splits sentences and tables and gives weaker retrieval.
- Section-aware chunking: more code and depends on headings, but retrieval is cleaner and citations can name the section.

## Extraction on filings (map-reduce)
Run the extraction prompt on each MD&A / financial-statement chunk, merge metrics by (name, basis, period), first value wins, and log a CONFLICT when two chunks disagree.

## Hand-check results (numbers checked against the filing text)
| Value | Verdict | Evidence |
|---|---|---|
| Revenue 215,938 | Correct | lines 1580, 3229 |
| Net income 120,067 | Correct | lines 1584, 2129 |
| Operating margin 60.4% | Correct | line 1680 |
| Gross margin 71.1% | Correct | lines 1581, 1675, 1744 |
| Revenue 22,459 | Wrong label: Graphics segment revenue | lines 1698, 3229 |
| Revenue 26,000 | Invented, not in the filing | no match |

## Failures found and fixes
1. Invented revenue 26,000 passed the first verifier, which only checked the model's own quote. Fix: agents/verify_source.py checks every value against the source chunk text.
2. Net income 55.6 "percent" was a % of revenue ratio. Fix: percent unit rejected for absolute amounts (revenue, net_income, free_cash_flow, operating_income, eps).
3. Segment revenue 22,459 reported as total revenue. Fix: FILING_RULES in the prompt (consolidated totals only).
4. Same metric kept twice because of period case ("Fiscal Year 2026" vs "fiscal year 2026"). Fix: lowercase period in the merge key.
5. Limit: the source check proves a number is not invented, not that it is the right line item. In one run it also dropped the correct revenue 215,938 because that chunk did not contain it, which is the safe direction.

## Open items (later days)
- Quote fragments are table-header text because pypdf flattens tables into one line (ask Sandeep about `| a | b |` table output).
- Numbers converted by the model (e.g. 215.9 billion) would be dropped. Tune on Day 7.
