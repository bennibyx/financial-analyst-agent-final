# Run: python scripts/check_pdf_risks.py
# Compares risk agent output on the PDF vs the TXT of the same call (Bug 3 check). Makes 2 model calls.
import sys; sys.path.insert(0, ".")
from pathlib import Path
from backend.app.parser import extract_text
from agents.risk import analyze_risk

def run(label, path):
    text = extract_text(Path(path))
    out = analyze_risk(text)
    res = out["result"]
    print(f"\n=== {label} ({len(text)} chars) ===")
    print(f"level={res['overall_risk_level']}  kept={out['quotes_kept']}/{out['quotes_total']}  retries={out['retries']}")
    for r in res["risks"]:
        print(f"  KEPT sev{r['severity']} {r['title']}: {r['quote'][:90]}")
    for i in out["issues"]:
        print("  ISSUE:", i[:140])

run("PDF", "data/sample/nvidia_Q4FY26_call.pdf")
run("TXT", "data/sample/nvidia_Q4FY26_call.txt")
