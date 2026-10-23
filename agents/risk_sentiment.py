# agents/risk_sentiment.py -- Risk & Sentiment Agent v1: one call, one structured JSON result
from .sentiment import analyze_sentiment
from .risk import analyze_risk

SCHEMA_VERSION = "1.1"

def _as_result(res):
    """analyze_sentiment returns (Sentiment, retries); analyze_risk returns a dict. Give both the dict shape."""
    if isinstance(res, tuple):
        obj, retries = res[0], (res[1] if len(res) > 1 else None)
        data = obj.model_dump() if hasattr(obj, "model_dump") else obj
        kept = len(data.get("evidence_quotes", [])) if isinstance(data, dict) else 0
        return {"result": data, "issues": [], "retries": retries, "quotes_kept": kept, "quotes_total": None}
    return res

def analyze_risk_sentiment(text):
    """Runs both agents. One failing agent never kills the other: its slot becomes null and the error is reported."""
    out = {"schema_version": SCHEMA_VERSION, "sentiment": None, "risk": None, "issues": [], "errors": {}}
    for key, fn in (("sentiment", analyze_sentiment), ("risk", analyze_risk)):
        try:
            res = _as_result(fn(text))
            out[key] = res["result"]
            out["issues"] += [f"{key}: {i}" for i in res["issues"]]
            out[key + "_quotes"] = {"kept": res["quotes_kept"], "total": res["quotes_total"]}
        except Exception as e:                       # keep going, report the failure
            out["errors"][key] = str(e)[:300]
    try:
        from .hedging import hedging_stats
        from .sentiment import hedging_level_from_density
        st = hedging_stats(text)
        out["hedging"] = {"level": hedging_level_from_density(st["strong_per_1000"]),
                          "strong_per_1000": st["strong_per_1000"], "evidence": st["strong"][:3]}
        sent = out.get("sentiment")
        if isinstance(sent, dict):
            sent["hedging_level"] = out["hedging"]["level"]      # code-computed, not the model's guess
            quotes = sent.get("evidence_quotes") or []
            if sent.get("qa_pushback") == "none" and any(str(q).startswith("PUSHBACK:") for q in quotes):
                sent["qa_pushback"] = "mild"
                out["issues"].append("sentiment: qa_pushback was none but a pushback quote exists, set to mild")
    except Exception as e:
        out["errors"]["hedging"] = str(e)[:200]
    return out
