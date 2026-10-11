import time, requests

BASE = "http://localhost:8000"
docs = sorted(requests.get(f"{BASE}/documents").json()["items"], key=lambda d: d["document_id"])
print(f"\n=== Extracting {len(docs)} documents (each can take 30-120 seconds) ===\n")

for d in docs:
    start = time.time()
    try:
        r = requests.post(f"{BASE}/extract/{d['document_id']}", timeout=200)
    except requests.RequestException as e:
        print(f"ERROR  {d['filename']}: {e}")
        continue
    secs = round(time.time() - start, 1)
    if r.status_code != 200:
        print(f"FAIL   {d['filename']}: HTTP {r.status_code} {r.text[:150]}")
        continue
    j = r.json()
    filled = sum(1 for m in j["metrics"] if m["value"] is not None)
    print(f"OK  {d['filename']} | {d['doc_type']} | metrics={len(j['metrics'])} "
          f"filled={filled} saved={j['saved_to_db']} issues={len(j['issues'])} | {secs}s")

if docs:
    print("\n=== Re-run check (should not create duplicates) ===")
    first = docs[0]["document_id"]
    before = len(requests.get(f"{BASE}/documents/{first}/metrics").json()["items"])
    r = requests.post(f"{BASE}/extract/{first}", timeout=200)
    after = len(requests.get(f"{BASE}/documents/{first}/metrics").json()["items"])
    print(f"stored before: {before} | saved by re-run: {r.json().get('saved_to_db')} | stored after: {after}")
    print("PASS: stored after equals saved by re-run" if after == r.json().get("saved_to_db")
          else "CHECK: counts differ")
