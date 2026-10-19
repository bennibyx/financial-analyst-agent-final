# Checks that /chat returns clean errors. Run: python scripts/chat_error_test.py [base_url]
import json, sys, urllib.request, urllib.error
BASE = sys.argv[1] if len(sys.argv) > 1 else "https://financial-analyst-agent-v1.onrender.com"

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, method=method, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()

cases = [  # (name, method, path, body, expected status)
    ("unknown document", "POST", "/chat", {"document_id": 9999, "message": "hi"}, 404),
    ("blank message", "POST", "/chat", {"document_id": 2, "message": "   "}, 422),
    ("empty message", "POST", "/chat", {"document_id": 2, "message": ""}, 422),
    ("message too long", "POST", "/chat", {"document_id": 2, "message": "x" * 2001}, 422),
    ("unknown conversation", "POST", "/chat", {"document_id": 2, "message": "hi", "conversation_id": 9999}, 404),
    ("get unknown conversation", "GET", "/chat/9999", None, 404),
]
bad = 0
for name, method, path, body, want in cases:
    status, text = call(method, path, body)
    ok = status == want
    bad += not ok
    print(("PASS" if ok else "FAIL"), name, "| got", status, "want", want, "|", text[:90])
print("\n%d/%d passed" % (len(cases) - bad, len(cases)))
