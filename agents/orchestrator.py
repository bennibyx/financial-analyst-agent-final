import hashlib
import json
import re
import sys
import time
import pathlib
from concurrent.futures import ThreadPoolExecutor

from .normalize import normalize_pdf_text
from .extraction_agent import run_extraction
from .risk_sentiment import analyze_risk_sentiment
from .analyst import answer_question

MAX_ANALYZE_CHARS = 60000
DEFAULT_QUESTION = "What were the key financial results and the main risks?"
METRIC_WORDS = ("revenue", "income", "eps", "margin", "earnings", "profit", "cash flow", "how much")
RISK_WORDS = ("risk", "sentiment", "tone", "hedg", "concern", "headwind", "outlook")


def as_dict(x):
    return x.model_dump() if hasattr(x, "model_dump") else x


def make_plan(question, tasks=None):
    if tasks:
        return [t for t in ("extract", "analyze", "ask") if t in tasks]
    if not question:
        return ["extract", "analyze"]
    q = question.lower()
    plan = ["ask"]
    if any(w in q for w in METRIC_WORDS):
        plan.append("extract")
    if any(w in q for w in RISK_WORDS):
        plan.append("analyze")
    return plan


def cross_check(ask_out, extract_out):
    answer = ((ask_out or {}).get("result") or {}).get("answer", "")
    metrics = (extract_out or {}).get("metrics", [])
    nums = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*(?:\.\d+)?", answer)]
    confirmed = []
    for m in metrics:
        v = m.get("value")
        if v is None:
            continue
        if m.get("unit") == "USD_million":
            hit = any(abs(n - v) < 0.5 or abs(n - v / 1000) <= 0.06 for n in nums)
        else:
            hit = any(abs(n - v) <= 0.051 for n in nums)
        if hit:
            confirmed.append({"metric": m["name"], "value": v})
    return {"answer_numbers": nums, "confirmed_by_extraction": confirmed}


def orchestrate(text, question=None, doc_id=None, tasks=None):
    text = normalize_pdf_text(text)
    doc_id = doc_id or "doc-" + hashlib.sha1(text.encode()).hexdigest()[:8]
    plan = make_plan(question, tasks)
    if "ask" in plan and not question:
        question = DEFAULT_QUESTION
    trace = []

    calls = {
        "extract": lambda: run_extraction(text, "auto", doc_id),
        "analyze": lambda: analyze_risk_sentiment(text[:MAX_ANALYZE_CHARS]),
        "ask": lambda: answer_question(question, text, doc_id=doc_id),
    }

    def run_step(name):
        t0 = time.time()
        try:
            out = as_dict(calls[name]())
            trace.append({"step": name, "ok": True, "seconds": round(time.time() - t0, 1)})
            return out
        except Exception as e:
            trace.append({"step": name, "ok": False, "seconds": round(time.time() - t0, 1),
                          "error": f"{type(e).__name__}: {str(e)[:200]}"})
            return None

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {name: pool.submit(run_step, name) for name in plan}
    results = {name: f.result() for name, f in futures.items()}

    checks = {}
    if results.get("ask") and results.get("extract"):
        checks["cross_check"] = cross_check(results["ask"], results["extract"])
    if "analyze" in plan and len(text) > MAX_ANALYZE_CHARS:
        checks["analyze_truncated_to_chars"] = MAX_ANALYZE_CHARS

    return {
        "doc_id": doc_id,
        "question": question,
        "plan": plan,
        "results": results,
        "checks": checks,
        "trace": sorted(trace, key=lambda t: t["step"]),
        "ok": all(t["ok"] for t in trace),
    }


if __name__ == "__main__":
    path = sys.argv[1]
    question = sys.argv[2] if len(sys.argv) > 2 else None
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    t0 = time.time()
    out = orchestrate(text, question, doc_id=pathlib.Path(path).stem)
    print("\nPLAN:", out["plan"], "| total seconds:", round(time.time() - t0, 1), "| all ok:", out["ok"])
    for t in out["trace"]:
        print("  ", t)
    ex = out["results"].get("extract")
    if ex:
        print("\nMETRICS:")
        for m in ex["metrics"]:
            print("  ", m["name"], m["value"], m["unit"], m["period"])
    an = out["results"].get("analyze")
    if an:
        print("\nSENTIMENT:", json.dumps(an.get("sentiment"), default=str)[:300])
        print("RISK:", json.dumps(an.get("risk"), default=str)[:400])
        print("ERRORS:", an.get("errors"))
    ask = out["results"].get("ask")
    if ask:
        print("\nANSWER:", (ask.get("result") or {}).get("answer"))
        print("ISSUES:", ask.get("issues"))
    print("\nCHECKS:", json.dumps(out["checks"], default=str)[:500])
    open("/tmp/orch.json", "w").write(json.dumps(out, indent=1, default=str))
    print("\nfull result saved to /tmp/orch.json")
