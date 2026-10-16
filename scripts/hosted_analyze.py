# Run: python scripts/hosted_analyze.py [document_id]   (default 2 = call PDF)
# Starts /analyze on the hosted service, polls /jobs/{id}, prints the risk summary.
import sys, json, time, urllib.request

BASE = "https://financial-analyst-agent-v1.onrender.com"
doc_id = sys.argv[1] if len(sys.argv) > 1 else "2"

def call(method, path):
    req = urllib.request.Request(BASE + path, method=method, data=b"" if method == "POST" else None)
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def find(obj, key):
    """Find the first value for `key` anywhere in nested JSON."""
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

start = call("POST", f"/analyze/{doc_id}")
print("START:", json.dumps(start)[:300])
job_id = find(start, "job_id") or find(start, "id")

for i in range(60):                      # up to ~5 min
    time.sleep(5)
    job = call("GET", f"/jobs/{job_id}")
    status = str(find(job, "status"))
    print(f"  poll {i+1}: {status}")
    if status.lower() in ("done", "completed", "complete", "succeeded", "failed", "error"):
        break

print("\nlevel:", find(job, "overall_risk_level"))
for r in find(job, "risks") or []:
    print(f"  sev{r.get('severity')} {r.get('title')}")
print("hedging_level:", find(job, "hedging_level"))
