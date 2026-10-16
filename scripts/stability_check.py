# Run: python scripts/stability_check.py [document_id] [runs]   (default: doc 2, 3 runs)
# Day 19: same document analyzed N times on the hosted service; shows how much the output varies.
import sys, json, time, urllib.request

BASE = "https://financial-analyst-agent-v1.onrender.com"
doc_id = sys.argv[1] if len(sys.argv) > 1 else "2"
runs = int(sys.argv[2]) if len(sys.argv) > 2 else 3

def call(method, path):
    req = urllib.request.Request(BASE + path, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

def find(obj, key):
    if isinstance(obj, dict):
        if key in obj: return obj[key]
        for v in obj.values():
            hit = find(v, key)
            if hit is not None: return hit
    elif isinstance(obj, list):
        for v in obj:
            hit = find(v, key)
            if hit is not None: return hit
    return None

results = []
for n in range(1, runs + 1):
    job = call("POST", f"/analyze/{doc_id}")
    for _ in range(60):
        time.sleep(5)
        job = call("GET", f"/jobs/{job['job_id']}")
        if str(job.get("status")).lower() in ("done", "failed", "error"):
            break
    risks = find(job, "risks") or []
    sent = find(job, "sentiment") or {}
    results.append({
        "level": find(job, "overall_risk_level"),
        "n": len(risks),
        "cats": sorted({r.get("category") for r in risks}),
        "sev": sorted([r.get("severity") for r in risks], reverse=True),
        "tone": sent.get("overall"), "score": sent.get("score"),
        "hedging": sent.get("hedging_level"), "pushback": sent.get("qa_pushback"),
    })
    print(f"run {n}: {results[-1]}")

levels = {r["level"] for r in results}
cats = [set(r["cats"]) for r in results]
common = set.intersection(*cats) if cats else set()
union = set.union(*cats) if cats else set()
print("\n--- stability summary ---")
print("risk level identical across runs:", len(levels) == 1, levels)
print("risk count per run:", [r["n"] for r in results])
print(f"risk categories in ALL runs: {len(common)} of {len(union)} seen -> {sorted(common)}")
print("tone score per run:", [r["score"] for r in results])
print("hedging identical:", len({r['hedging'] for r in results}) == 1,
      "| pushback identical:", len({r['pushback'] for r in results}) == 1)
