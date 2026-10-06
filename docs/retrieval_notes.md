# Retrieval Notes (Day 5)

## Setup
- Embedding model: Qwen/Qwen3-Embedding-8B via Nebius Token Factory (4096 dimensions). Token Factory listed no NVIDIA embedding model for our key; Nemotron handles all extraction and reasoning.
- Index: 103 chunks from the NVIDIA Q4 FY26 10-K, embedded in batches of 16, normalized, cosine similarity with numpy, cached in data/index/ (gitignored).
- Code: agents/retrieval.py, scripts/day5_retrieval.py, scripts/diag_dc.py. Run: python3 -m scripts.day5_retrieval

## Results (top 3 per query)
| Query | Verdict | Notes |
|---|---|---|
| What are the supply chain risks? | Good | Top 3 are risk_factors chunks on suppliers and the supply chain. The top hit (score 0.650) is the section intro, so a high score does not mean the best answer. |
| How did data center revenue change? | Good (3/3) | Verified with scripts/diag_dc.py: ranks 1, 2, 3 hold the answer (mdna-2: Data Center revenue up 68%; mdna-5: networking up 142%; financial_statements-29: Data Center $193,737M vs $115,186M). |
| What are the export restrictions? | Good | risk_factors-21 and -22 discuss export controls. The top hit (other-12) is a risk-style list in the "other" section; its section label is unchecked. |

## Findings
1. Scores sit between 0.5 and 0.65 and do not separate good from weak hits. The intro chunk outscored the real answers, so do not use a fixed score threshold.
2. Judge a hit by whether the chunk contains the answer, not by its first 200 characters (chunks are up to 4,000 characters).
3. Boilerplate chunks (section intros) can rank first.
4. Only the 10-K was tested. The earnings-call transcript (no Item headings, fixed-size fallback) is untested.

## Planned improvements
- Return the top 5 chunks and let the Q&A agent (Day 12) read all of them, then cite chunk_id and section.
- Optional: Nemotron re-ranking or hybrid keyword search if misses appear.
- Check other-12 and the Item 1A section pattern.
- Test retrieval on the transcript.
- Turn these queries into a retrieval hit-rate check in Alekhya's evaluation set (answer-marker found in top-k).
