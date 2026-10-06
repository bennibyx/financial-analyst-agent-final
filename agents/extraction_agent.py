# agents/extraction_agent.py -- Extraction Agent v1: ONE entry point for transcripts and filings
import re
from .extraction import extract                       # transcript path: returns (result, retries)
from .extract_filing import extract_filing            # filing path: returns a list of Metric
from .verify import verify, clean_text                # check 1: quote found in source, number in quote
from .verify_source import check_against_source       # check 2: number found in source text

def detect_doc_type(text):
    """Filings have 'Item 1A. Risk Factors' on its own line; transcripts do not."""
    return "filing" if re.search(r"^[ \t]*item\s+1a", text, flags=re.I | re.M) else "transcript"

def run_extraction(text, doc_type="auto", doc_id="doc", max_chunks=5):
    """Returns {"doc_type", "metrics", "guidance", "issues", "retries"}; metrics/guidance are plain dicts."""
    if doc_type == "auto":
        doc_type = detect_doc_type(text)
    if doc_type == "filing":
        metrics = extract_filing(text, doc_id, max_chunks=max_chunks)   # verifies inside, per chunk
        return {"doc_type": "filing", "metrics": [m.model_dump() for m in metrics],
                "guidance": [], "issues": [], "retries": None}           # MVP: no guidance for filings yet
    text = clean_text(text)
    result, retries = extract(text)                                      # schema-validated, retries on bad JSON
    result, issues, fixes = verify(result, text)
    result, src_issues = check_against_source(result, text)
    return {"doc_type": "transcript", "metrics": [m.model_dump() for m in result.metrics],
            "guidance": [g.model_dump() for g in result.guidance],
            "issues": issues + src_issues + fixes, "retries": retries}
