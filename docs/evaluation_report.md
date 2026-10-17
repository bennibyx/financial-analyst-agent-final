# Evaluation Report (draft, Day 21)

All numbers below were measured on the NVIDIA FY2026 10-K and Q4 FY26 earnings call. Rows marked TBD are not measured yet.

## 1. Extraction accuracy (5 documents, answer keys)
- 28/28 headline values correct, 0 hallucinated values.
- Source quotes found in the document: 17/22 (PDF citations are the weakest).
- TBD: split of values extracted by the model vs recovered by the table-row fallback (not counted yet; do not claim "all by Nemotron").

## 2. Q&A (/chat) on a 9-question starter set (one document, 10-K)
| Run | Server image | Correct | Citations grounded in source |
|---|---|---|---|
| 1 | v7 | 7/9 | 7/7 |
| 2 | v8 | 8/9 | 13/13 |
| 3 | v8 | 9/9 | 13/13 |
- Repeat checks on v8: operating income 5/5 correct, diluted EPS 5/5 correct, unanswerable question abstained 3/3.
- No wrong figures observed in v7/v8 runs; all misses were false abstains (the strict number check abstains rather than guesses).
- TBD: accuracy on the 20-question set (waiting for the final set).

## 3. Risk and sentiment stability (hosted v6, call PDF, 6 repeat runs)
- Risk level "high" in 6/6 runs (7/8 across all runs; one earlier run gave "medium").
- 4 to 5 risks per run; competition, regulatory/export and supply chain risks found in all 6 runs.
- Tone score 0.75, hedging level and Q&A pushback identical in every run.

## 4. Model benchmark (Nebius Token Factory, 23 extraction values)
| Model | Result | Time |
|---|---|---|
| Nemotron 3 Nano 30B | 23/23 in 5/5 runs | 28-48 s |
| Nemotron 3 Super 120B | 23/23 in 4/4 runs | 29-34 s |
| Nemotron 3.5 Lightning | 23/23 in 1/4 runs | n/a |
| Qwen3-30B | 23/23 | 482 s |
| gpt-oss-120b | 19/23 (4 missing, 0 wrong) | n/a |
- TBD: price per 1M tokens and the final default-model decision.

## 5. Hallucination controls
- Every number in an answer must appear in its cited source sentences, otherwise the answer is replaced by "The document does not say."
- Citations are sentence IDs resolved by code, then checked against the document text.
- Unanswerable questions abstain (3/3 repeat runs).

## 6. Known limitations (state these in the README)
- The Q&A set is small and covers one document; broader accuracy is TBD.
- Plain years and period labels are not verified by the number check.
- The model sometimes returns badly formatted JSON; retries and a double-check before abstaining reduce but do not remove false abstains.
- PDF and text versions of the same document give slightly different hedging scores; hedging bands are provisional, tuned on 3 NVIDIA calls.
- The hosted demo runs on a free tier and may sleep or reset its data.
