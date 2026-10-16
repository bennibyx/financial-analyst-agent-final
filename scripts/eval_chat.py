# Day 21: evaluate /chat answers and citations against a question set.
# Run from repo root:  python scripts/eval_chat.py [qa_file] [base_url]
# Question format: {"id","doc","question","answer_any":[accepted strings]} ; "expect_abstain": true for unanswerable questions.
# Items without answer_any are printed for manual review (not scored).
import sys, json, re, time, pathlib, datetime, urllib.request
sys.path.insert(0, ".")
from backend.app.parser import extract_text

QA = sys.argv[1] if len(sys.argv) > 1 else "agents/eval/qa_starter.json"
BASE = sys.argv[2] if len(sys.argv) > 2 else "https://financial-analyst-agent-v1.onrender.com"
ABSTAIN = ("not ", "no information", "does not", "doesn't", "cannot", "can't", "unable", "isn't", "no data", "not available")

def http(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, method=method, data=data, headers={"Content-Type": "application/json"})
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

def collect(obj, key, out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        if key in obj: out.append(obj)
        for v in obj.values(): collect(v, key, out)
    elif isinstance(obj, list):
        for v in obj: collect(v, key, out)
    return out

def squash(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
def norm(s): return (s or "").lower().replace(",", "")
def strings(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, str): out.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values(): strings(v, out)
    elif isinstance(obj, list):
        for v in obj: strings(v, out)
    return out

items = json.loads(pathlib.Path(QA).read_text())
hosted = {d["filename"]: (d.get("id", d.get("document_id"))) for d in collect(http("GET", "/documents"), "filename")}
text_cache = {}
rows = []
for it in items:
    doc = it["doc"]
    if doc not in hosted:
        print(f"{it['id']}: SKIP, {doc} is not on the server (seed it first)"); continue
    if doc not in text_cache:
        text_cache[doc] = squash(extract_text(pathlib.Path(it.get("source_file", f"data/sample/{doc}"))))
    t = time.time()
    try:
        resp = http("POST", "/chat", {"document_id": hosted[doc], "message": it["question"]})
    except Exception as e:
        rows.append({"id": it["id"], "status": "ERROR", "detail": str(e)[:120]}); print(it["id"], "ERROR", e); continue
    secs = round(time.time() - t, 1)
    answer = str(find(resp, "answer") or find(resp, "content") or "")
    cites = find(resp, "citations") or []
    checkable = grounded = 0
    for c in cites:
        long_strs = [s for s in strings(c) if len(s) > 15]
        if long_strs:
            checkable += 1
            if any(squash(s) in text_cache[doc] for s in long_strs): grounded += 1
    if it.get("expect_abstain"):
        status = "OK_ABSTAIN" if any(a in answer.lower() + " " for a in ABSTAIN) else "WRONG_NO_ABSTAIN"
    elif it.get("answer_any"):
        status = "CORRECT" if any(norm(a) in norm(answer) for a in it["answer_any"]) else "WRONG"
    else:
        status = "REVIEW"
    rows.append({"id": it["id"], "status": status, "secs": secs, "cites": len(cites), "checkable": checkable,
                 "grounded": grounded, "answer": answer})
    print(f"{it['id']:<4}{status:<18}{secs:>5}s  cites={len(cites)} grounded={grounded}/{checkable}  | {answer[:110]!r}", flush=True)

scored = [r for r in rows if r["status"] in ("CORRECT", "WRONG", "OK_ABSTAIN", "WRONG_NO_ABSTAIN")]
good = sum(1 for r in scored if r["status"] in ("CORRECT", "OK_ABSTAIN"))
answered = [r for r in rows if "cites" in r and r["status"] != "OK_ABSTAIN"]
with_cite = sum(1 for r in answered if r["cites"] > 0)
chk = sum(r["checkable"] for r in rows if "checkable" in r); gnd = sum(r["grounded"] for r in rows if "grounded" in r)
summary = (f"Questions scored: {len(scored)} | correct: {good}/{len(scored)}\n"
           f"Answers with at least one citation: {with_cite}/{len(answered)}\n"
           f"Citations whose text is found in the document: {gnd}/{chk} (checkable)\n"
           f"Not scored (manual review): {sum(1 for r in rows if r['status']=='REVIEW')}")
print("\n" + summary)
ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
pathlib.Path(f"docs/chat_eval_runs/chat_{ts}.json").write_text(json.dumps(rows, indent=2))   # local only (gitignored)
pathlib.Path("docs/chat_eval_summary.md").write_text(f"# /chat evaluation ({ts}, {QA})\n\n" + summary + "\n")
print(f"saved docs/chat_eval_summary.md (numbers only) and docs/chat_eval_runs/chat_{ts}.json (local)")
