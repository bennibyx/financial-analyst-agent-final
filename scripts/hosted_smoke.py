# Run: python scripts/hosted_smoke.py
# Day 18 smoke test of the HOSTED service. Prints a pass/fail table and writes docs/integration_signoff.md.
import sys, json, time, datetime, urllib.request, urllib.error

BASE = "https://financial-analyst-agent-v1.onrender.com"
IMAGE_TAG = "bennibyx/financial-analyst-agent:v5"   # confirm this matches what Render runs

def http(method, path, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read())
        except Exception: return e.code, None

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

def collect(obj, key, out=None):
    """All dicts anywhere in the JSON that contain `key`."""
    out = [] if out is None else out
    if isinstance(obj, dict):
        if key in obj: out.append(obj)
        for v in obj.values(): collect(v, key, out)
    elif isinstance(obj, list):
        for v in obj: collect(v, key, out)
    return out

def run_maybe_job(method, path, body=None):
    """If the endpoint returns a background job, poll /jobs/{id} until it finishes."""
    code, js = http(method, path, body)
    if code in (200, 202) and isinstance(js, dict) and js.get("job_id") and js.get("status") in ("queued", "running"):
        for _ in range(60):
            time.sleep(5)
            code, js = http("GET", f"/jobs/{js['job_id']}")
            if str(find(js, "status")).lower() in ("done", "completed", "failed", "error"):
                break
    return code, js

rows = []
def check(name, fn):
    t = time.time()
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"error: {e}"
    secs = round(time.time() - t, 1)
    rows.append((name, "PASS" if ok else "FAIL", secs, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  ({secs}s)  {detail}")

# --- cold start + health
def t_health():
    code, js = http("GET", "/health", timeout=180)
    return code == 200 and js.get("status") == "ok", f"HTTP {code}"
check("GET /health (includes cold start)", t_health)

# --- find the demo documents by type
code, docs_js = http("GET", "/documents")
docs = collect(docs_js, "doc_type")
tenk = next((d["id"] if "id" in d else d.get("document_id") for d in docs if d["doc_type"] == "10-K"), None)
call = next((d["id"] if "id" in d else d.get("document_id") for d in docs if d["doc_type"] == "transcript"), None)
check("GET /documents has 10-K + transcript", lambda: (tenk is not None and call is not None, f"10-K id={tenk}, call id={call}"))
if tenk is None or call is None:
    print("\nDemo documents missing. Run: bash scripts/seed_demo.sh " + BASE); sys.exit(1)

def t_extract():
    code, js = run_maybe_job("POST", f"/extract/{tenk}")
    m = find(js, "metrics") or []
    return code == 200 and len(m) > 0, f"HTTP {code}, {len(m)} metrics"
check(f"POST /extract/{tenk} (10-K)", t_extract)

def t_metrics():
    code, js = http("GET", f"/documents/{tenk}/metrics")
    items = (js or {}).get("items", []) if isinstance(js, dict) else []
    bad = [f"{i['name']}={i['value']}" for i in items if i.get("unit") == "percent" and i.get("value", 0) > 100]
    return code == 200 and bool(items) and not bad, f"{len(items)} metrics" + (f"; IMPLAUSIBLE percent: {bad}" if bad else "")
check(f"GET /documents/{tenk}/metrics", t_metrics)

def t_analyze():
    code, js = run_maybe_job("POST", f"/analyze/{call}")
    risks = find(js, "risks") or []
    level = find(js, "overall_risk_level")
    return code == 200 and len(risks) > 0 and level != "unknown", f"level={level}, {len(risks)} risks"
check(f"POST /analyze/{call} (call)", t_analyze)

def t_chat():
    code, js = http("POST", "/chat", {"document_id": call, "message": "What did management say about supply constraints?"})
    ans = find(js, "answer") or find(js, "content") or ""
    cites = find(js, "citations") or []
    return code == 200 and bool(ans) and len(cites) > 0, f"HTTP {code}, answer {len(str(ans))} chars, {len(cites)} citations"
check("POST /chat (with citations)", t_chat)

def t_trends():
    code, js = http("GET", "/trends")
    return code == 200 and bool(js), f"HTTP {code}"
check("GET /trends", t_trends)

def t_brief():
    code, js = run_maybe_job("POST", f"/brief/{call}")
    return code == 200 and bool(js), f"HTTP {code}, {len(json.dumps(js))} chars"
check(f"POST /brief/{call}", t_brief)

def t_compare():
    code, js = http("GET", "/compare")
    return code in (200, 422), f"HTTP {code} (422 = needs params, endpoint exists)"
check("GET /compare", t_compare)

# --- write the sign-off file
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
passed = sum(1 for r in rows if r[1] == "PASS")
lines = [f"# Day 18 Integration Sign-off", "",
         f"- Date: {now}", f"- Hosted URL: {BASE}", f"- Image: {IMAGE_TAG}",
         f"- Result: {passed}/{len(rows)} checks passed", "",
         "| Check | Result | Seconds | Detail |", "|---|---|---|---|"]
lines += [f"| {n} | {s} | {t} | {d} |" for n, s, t, d in rows]
open("docs/integration_signoff.md", "w").write("\n".join(lines) + "\n")
print(f"\n{passed}/{len(rows)} passed. Wrote docs/integration_signoff.md")
