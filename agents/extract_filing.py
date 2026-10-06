# agents/extract_filing.py -- map-reduce extraction over filing chunks
import json, sys, pathlib
from .schemas import ExtractionResult
from .llm import ask_json
from .verify import verify, clean_text
from .verify_source import check_against_source   # number must exist in the source chunk
from .extraction import SYSTEM
from .chunking import chunk_document

# The only metric names the schema accepts
ALLOWED_METRICS = {"revenue", "eps", "gross_margin", "operating_margin", "net_income", "free_cash_flow"}

# Extra rules for filings (appended to the transcript prompt, extraction.py stays untouched)
FILING_RULES = """

ADDITIONAL RULES FOR SEC FILINGS:
- Report only CONSOLIDATED company totals. Never report a segment row (Graphics, Compute & Networking, a region, a product line) as company revenue or income.
- The value must be a number written in the text, copied exactly. Do not compute, round or convert it.
- The period must match the table heading it came from (e.g. "Year Ended Jan 25, 2026" = Fiscal Year 2026, not a quarter).
- A figure shown as "% of revenue" is a margin in percent, never an absolute amount.
- If a total is not clearly shown in this section, return no metric for it.
- Metric names must be EXACTLY one of: revenue, eps, gross_margin, operating_margin, net_income, free_cash_flow. Never output any other metric (for example operating_expenses); simply leave it out."""

def drop_unknown_metrics(data):
    """Runs on the parsed JSON BEFORE Pydantic: delete metrics with a name the schema rejects."""
    kept = []
    for m in data.get("metrics", []):
        if isinstance(m, dict) and m.get("name") in ALLOWED_METRICS:
            kept.append(m)
        else:
            print("   FILTERED unknown metric:", m.get("name") if isinstance(m, dict) else m, flush=True)
    data["metrics"] = kept
    return data

def extract_chunk(chunk):
    schema = json.dumps(ExtractionResult.model_json_schema(), indent=1)
    user = ("Extract company, period, key metrics and any forward guidance from this "
            f"section of an SEC filing:\n\n<transcript>\n{chunk.text}\n</transcript>")
    system = SYSTEM.replace("{schema}", schema) + FILING_RULES
    try:
        result, _ = ask_json(system, user, ExtractionResult, pre=drop_unknown_metrics)
    except RuntimeError as e:                                       # all retries failed: skip, do not crash
        msg = f"chunk {chunk.chunk_id} skipped: {str(e)[:100]}"
        print("   SKIPPED:", msg, flush=True)
        return None, [msg]
    print("   RAW:", [(m.name, m.value) for m in result.metrics], flush=True)   # model output, before checks
    result, issues, fixes = verify(result, chunk.text)              # check 1: quote + number in quote
    result, src_issues = check_against_source(result, chunk.text)   # check 2: number in source text
    for i in src_issues:
        print("   DROPPED:", i, flush=True)
    return result, issues + src_issues

def extract_filing(text, doc_id, max_chunks=5):
    chunks = chunk_document(clean_text(text), doc_id)
    wanted = [c for c in chunks if c.section in ("mdna", "financial_statements")] or chunks
    merged = {}
    for c in wanted[:max_chunks]:
        print(f"  chunk {c.chunk_id} ({len(c.text)} chars)", flush=True)
        res, issues = extract_chunk(c)
        if res is None:                                             # skipped chunk
            continue
        for m in res.metrics:
            if m.value is None:
                continue
            key = (m.name, m.basis, (m.period or "").strip().lower())   # lowercase: merges duplicates
            if key not in merged:                                       # first real value wins (MVP)
                merged[key] = m
            elif merged[key].value != m.value:
                print(f"   CONFLICT: {key} kept {merged[key].value}, saw {m.value}", flush=True)
    return list(merged.values())

if __name__ == "__main__":
    path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    text = open(path, encoding="utf-8").read()
    for m in extract_filing(text, doc_id=pathlib.Path(path).stem, max_chunks=limit):
        print(m.name, m.basis, m.value, m.unit, m.period, "|", m.source_quote[:80])
