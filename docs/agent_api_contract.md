# Agent-API Contract v1.0

The backend reaches the agents through `agents/service.py`. Every function returns an Envelope and never raises.

## Envelope
{ "ok": bool, "data": {...}|null, "error": {"code","message"}|null,
  "meta": {"agent","latency_ms","doc_id","contract_version","used_fallback","fallback_reason"} }

## Functions
| Function | Backend route | Input | data contains |
|---|---|---|---|
| extract_document(text, doc_type="auto", doc_id=None) | POST /extract/{document_id} | document text | metrics + guidance, each with source_quote |
| analyze_document(text, doc_id=None) | POST /analyze/{document_id} (background job) | transcript text | risk + sentiment JSON |
| ask_document(question, text, doc_id=None) | POST /chat | standalone question + text | answer, citations (doc_id, quote), answered flag |
| run_pipeline(text, question=None, doc_id=None) | planned: /brief | text, optional question | extract + analyze + answer, cross-checked |

## Rules
- Errors: BAD_INPUT (empty or too-short text, empty question), TIMEOUT, INTERNAL.
- doc_id: if omitted it is a hash of the text, so the same text reuses the cached search index and different text never gets a stale one.
- History: the agents are single-turn. The backend rewrites follow-ups into a standalone question before calling ask_document.
- Citations: every number in an answer must appear in a cited quote, otherwise answered=false.
- Slow calls: extract ~20 s, first ask on a new document builds an embedding index (allow 150 s), analyze runs as a background job (allow 300 s).

## Test
python3 scripts/contract_test.py  (11 checks, all must PASS)

## Frontend note: hedging
Use the top-level `hedging` block (code-measured, with evidence quotes) for the tone gauge. `sentiment.hedging_level` is model-judged and can disagree; do not show both.
