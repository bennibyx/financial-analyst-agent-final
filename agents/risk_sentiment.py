# agents/risk_sentiment.py -- Risk & Sentiment Agent v1: one call, one structured JSON result
from .sentiment import analyze_sentiment
from .risk import analyze_risk

SCHEMA_VERSION = "1.1"

def analyze_risk_sentiment(text):
    """Runs both agents. One failing agent never kills the other: its slot becomes null and the error is reported."""
    out = {"schema_version": SCHEMA_VERSION, "sentiment": None, "risk": None, "issues": [], "errors": {}}
    for key, fn in (("sentiment", analyze_sentiment), ("risk", analyze_risk)):
        try:
            res = fn(text)
            out[key] = res["result"]
            out["issues"] += [f"{key}: {i}" for i in res["issues"]]
            out[key + "_quotes"] = {"kept": res["quotes_kept"], "total": res["quotes_total"]}
        except Exception as e:                       # keep going, report the failure
            out["errors"][key] = str(e)[:300]
    return out
