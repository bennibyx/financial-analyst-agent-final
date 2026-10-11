# agents/extraction_agent.py -- Extraction Agent v1: ONE entry point for transcripts and filings
import re
from .extraction import extract                       # transcript path: returns (result, retries)
from .extract_filing import extract_filing            # filing path: returns a list of Metric
from .verify import verify, clean_text                # check 1: quote found in source, number in quote
from .verify_source import check_against_source       # check 2: number found in source text

from .normalize import normalize_pdf_text
from .transcript_fallback import transcript_fallback

def _with_fallback(metrics, text, period):
    """Add numbers the model missed but the transcript states in a plain past-tense sentence."""
    for m in transcript_fallback(text, period):
        d = m.model_dump()
        dup = any(x["name"] == d["name"] and (x.get("basis") == d.get("basis") or
                  (x.get("basis") is None and abs((x.get("value") or 0) - d["value"]) < 0.01)) for x in metrics)
        if not dup:
            metrics.append(d)
            print(f"   FALLBACK added {d['name']} {d.get('basis')} {d['value']} from transcript sentence", flush=True)
    return metrics

def _tidy(metrics):
    """Drop blank metrics and use ONE money unit (USD_million) so filings and calls are comparable."""
    out = []
    for m in metrics:
        if m.get("value") is None:
            continue
        if m.get("unit") == "USD_billion":
            m["value"] = round(m["value"] * 1000, 3)
            m["unit"] = "USD_million"
        out.append(m)
    return out

def detect_doc_type(text):
    """Filings have 'Item 1A. Risk Factors' on its own line; transcripts do not."""
    return "filing" if re.search(r"^[ \t]*item\s+1a", text, flags=re.I | re.M) else "transcript"

def run_extraction(text, doc_type="auto", doc_id="doc", max_chunks=4):
    """Returns {"doc_type", "metrics", "guidance", "issues", "retries"}; metrics/guidance are plain dicts."""
    if doc_type == "auto":
        doc_type = detect_doc_type(text)
    if doc_type == "filing":
        metrics = extract_filing(text, doc_id, max_chunks=max_chunks)   # verifies inside, per chunk
        return {"doc_type": "filing", "metrics": _tidy([m.model_dump() for m in metrics]),
                "guidance": [], "issues": [], "retries": None}           # MVP: no guidance for filings yet
    text = clean_text(normalize_pdf_text(text))
    result, retries = extract(text)                                      # schema-validated, retries on bad JSON
    result, issues, fixes = verify(result, text)
    result, src_issues = check_against_source(result, text)
    return {"doc_type": "transcript", "metrics": _with_fallback(_tidy([m.model_dump() for m in result.metrics]), text, result.period),
            "guidance": [g.model_dump() for g in result.guidance],
            "issues": issues + src_issues + fixes, "retries": retries}
