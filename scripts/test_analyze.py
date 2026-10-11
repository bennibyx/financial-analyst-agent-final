import os, sys, time, requests

BASE = "http://localhost:8000"
sys.path.insert(0, os.path.abspath("backend"))
os.chdir("backend")  # so the DB check reads the same SQLite file as the server


def poll(job_id, timeout=400):
    start = time.time()
    while time.time() - start < timeout:
        j = requests.get(f"{BASE}/jobs/{job_id}").json()
        if j["status"] in ("done", "failed"):
            return j, round(time.time() - start, 1)
        time.sleep(3)
    return {"status": "timeout"}, timeout


def risk_rows(doc_id):
    from app.database import SessionLocal
    from app.models import Risk
    db = SessionLocal()
    try:
        return db.query(Risk).filter(Risk.source_document_id == doc_id).count()
    finally:
        db.close()


docs = sorted(requests.get(f"{BASE}/documents").json()["items"], key=lambda d: d["document_id"])
targets = [d for d in docs if d["doc_type"] in ("transcript", "commentary")]
filings = [d for d in docs if d["doc_type"] in ("10-K", "10-Q")]

print(f"\n=== Analyzing {len(targets)} documents ===\n")
for d in targets:
    r1 = requests.post(f"{BASE}/analyze/{d['document_id']}")
    r2 = requests.post(f"{BASE}/analyze/{d['document_id']}")
    if r1.status_code != 202:
        print(f"FAIL {d['filename']}: HTTP {r1.status_code} {r1.text[:150]}")
        continue
    same = r1.json()["job_id"] == r2.json()["job_id"]
    j, secs = poll(r1.json()["job_id"])
    res = j.get("result") or {}
    risks = (res.get("risk") or {}).get("risks", [])
    sent = (res.get("sentiment") or {}).get("overall")
    print(f"{j['status'].upper():6} {d['filename']} | {secs}s | sentiment={sent} | risks={len(risks)} "
          f"| errors={res.get('errors') or '-'} | no-duplicate-job={'yes' if same else 'NO'}")
    saved = requests.get(f"{BASE}/documents/{d['document_id']}/analysis").status_code
    print(f"       saved analysis endpoint: HTTP {saved} (expected 200)")

if targets:
    first = targets[0]
    r = requests.post(f"{BASE}/analyze/{first['document_id']}")
    j, _ = poll(r.json()["job_id"])
    kept = len(((j.get("result") or {}).get("risk") or {}).get("risks", []))
    rows = risk_rows(first["document_id"])
    print(f"\n=== Re-run check on {first['filename']} ===")
    print(f"risks in result: {kept} | rows in risks table: {rows}")
    print("PASS: no duplicate rows" if kept == rows else "CHECK: counts differ")

print("\n=== Error checks ===")
if filings:
    r = requests.post(f"{BASE}/analyze/{filings[0]['document_id']}")
    print("filing    ->", r.status_code, r.text[:140])
r = requests.post(f"{BASE}/analyze/999999")
print("bad doc   ->", r.status_code, r.text[:140])
r = requests.get(f"{BASE}/jobs/999999")
print("bad job   ->", r.status_code, r.text[:140])
