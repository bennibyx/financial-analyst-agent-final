import sys, time, pathlib, requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
DOCS = sorted(p for p in pathlib.Path("data/test5").iterdir() if p.is_file() and not p.name.startswith("."))
results = []

def wait_until_done(doc_id, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        r = requests.get(f"{BASE}/documents/{doc_id}")
        if r.status_code != 200:
            return {"status": f"status_check_http_{r.status_code}"}, round(time.time() - start, 1)
        d = r.json()
        if d["status"] in ("indexed", "failed"):
            return d, round(time.time() - start, 1)
        time.sleep(2)
    return {"status": "timeout"}, timeout

print(f"\n=== Uploading {len(DOCS)} documents to {BASE} ===\n")
for f in DOCS:
    with open(f, "rb") as fh:
        r = requests.post(f"{BASE}/upload", files={"file": (f.name, fh)})
    if r.status_code != 200:
        print(f"FAIL  {f.name}: HTTP {r.status_code} {r.text[:150]}")
        results.append((f.name, "upload_failed", 0, 0))
        continue
    doc_id = r.json()["document_id"]
    d, secs = wait_until_done(doc_id)
    print(f"{d['status'].upper():8} {f.name} | chunks={d.get('chunk_count')} | {secs}s | {d.get('error_message') or ''}")
    results.append((f.name, d["status"], d.get("chunk_count"), secs))

print("\n=== Duplicate check ===")
if DOCS:
    with open(DOCS[0], "rb") as fh:
        r = requests.post(f"{BASE}/upload", files={"file": (DOCS[0].name, fh)})
    print("duplicate flag:", r.json().get("duplicate"), "(expected True)")

print("\n=== Error-shape checks ===")
r = requests.post(f"{BASE}/upload", files={"file": ("empty.pdf", b"")})
print("empty file ->", r.status_code, r.text[:200])
r = requests.post(f"{BASE}/upload", files={"file": ("bad.exe", b"MZ123")})
print("bad type   ->", r.status_code, r.text[:200])
r = requests.get(f"{BASE}/documents/999999")
print("not found  ->", r.status_code, r.text[:200])

ok = sum(1 for x in results if x[1] == "indexed")
print(f"\nSUMMARY: {ok}/{len(results)} indexed")
