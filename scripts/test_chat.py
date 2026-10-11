import time, requests

BASE = "http://localhost:8000"
H = {"Content-Type": "application/json"}


def chat(doc, msg, conv=None):
    body = {"document_id": doc, "message": msg}
    if conv:
        body["conversation_id"] = conv
    start = time.time()
    r = requests.post(f"{BASE}/chat", json=body, headers=H, timeout=200)
    return r, round(time.time() - start, 1)


def show(label, r, secs):
    if r.status_code != 200:
        print(f"FAIL {label}: HTTP {r.status_code} {r.text[:160]}")
        return None
    j = r.json()
    print(f"OK   {label} | {secs}s | answered={j['answered']} | citations={len(j['citations'])} "
          f"| rewritten={j['rewritten_question']!r}")
    print(f"     answer: {j['answer'][:150]}")
    return j


print("\n=== Conversation on doc 2 (TXT transcript) ===")
r, s = chat(2, "What did management say about supply constraints?")
j1 = show("first question", r, s)
conv = j1["conversation_id"] if j1 else None
if conv:
    r, s = chat(2, "How much of that supply is available?", conv)
    show("follow-up (needs history)", r, s)
    c = requests.get(f"{BASE}/chat/{conv}").json()
    roles = [m["role"] for m in c["messages"]]
    print("history roles:", roles, "| PASS" if roles == ["user", "assistant"] * 2 else "| CHECK")

print("\n=== New conversation on doc 5 (PDF transcript, builds index on first question) ===")
r, s = chat(5, "What did management say about data center revenue?")
j5 = show("first question", r, s)

print("\n=== Error checks ===")
r, _ = chat(999999, "hi")
print("bad document      ->", r.status_code, r.text[:110])
r, _ = chat(2, "hi", 999999)
print("bad conversation  ->", r.status_code, r.text[:110])
if conv:
    r, _ = chat(5, "hi", conv)
    print("wrong document    ->", r.status_code, r.text[:110])
r, _ = chat(2, "   ")
print("blank message     ->", r.status_code, r.text[:110])
r = requests.get(f"{BASE}/chat/999999")
print("history not found ->", r.status_code, r.text[:110])
