# Retrieval Notes (Day 5)

## Setup
- Embedding model: Qwen/Qwen3-Embedding-8B via Nebius Token Factory (4096 dimensions). Token Factory listed no NVIDIA embedding model for our key; Nemotron handles all extraction and reasoning.
- Index: 103 chunks from the NVIDIA Q4 FY26 10-K, embedded in batches of 16, normalized, cosine similarity with numpy, cached in data/index/ (gitignored).
- Code: agents/retrieval.py, scripts/day5_retrieval.py. Run: python3 -m scripts.day5_retrieval

## Results (top 3 per query)
| Query | Verdict | Notes |
|---|---|---|
| What are the supply chain risks? | Good | Top 3 are risk_factors chunks on suppliers and supply chain. Top hit (score 0.650) is the section intro, so score is not quality. |
| How did data center revenue change? | Weak | Top 3 are the FY26 summary table, a percent-of-revenue table and revenue by country. The filing reports segments as Compute & Networking and Graphics, so "data center" is a vocabulary mismatch. |
| What are the export restrictions? | Good | risk_factors-21 and -22 discuss export controls. Top hit (other-12) is a risk-style list that landed in "other" because the heading pattern misses part of Item 1A. |

## Findings
1. Scores sit between 0.5 and 0.65 and do not separate good from weak hits, so do not use a fixed score threshold yet.
2. Pure embedding search misses vocabulary differences (data center vs Compute & Networking).
3. Intro or boilerplate chunks can rank first.
4. Some risk-factor text sits in the "other" section.

## Planned improvements (Day 12, not now)
- Query rewriting: let Nemotron expand the question with filing vocabulary before searching.
- Hybrid search: add keyword matching to the embedding score.
- Fix section patterns so Item 1 and the rest of Item 1A are labelled correctly.
- Always return chunk_id and section so the Q&A agent can cite them.
