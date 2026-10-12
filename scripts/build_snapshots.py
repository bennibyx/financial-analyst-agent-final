"""scripts/build_snapshots.py - run extraction + hedging ONCE per call and save data/trends/<label>.json
Run: python3 scripts/build_snapshots.py"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.extraction_agent import run_extraction
from agents.hedging import hedging_stats

CALLS = {"Q4FY26": "nvidia_Q4FY26_call", "Q1FY27": "nvidia_Q1FY27_call", "Q2FY27": "nvidia_Q2FY27_call"}
SAMPLE = pathlib.Path("data/sample")
OUT = pathlib.Path("data/trends"); OUT.mkdir(parents=True, exist_ok=True)

def load_text(stem):
    txt = SAMPLE / f"{stem}.txt"
    if txt.exists():
        return txt.read_text(encoding="utf-8", errors="replace")
    from pypdf import PdfReader                      # no .txt for this call: read the PDF
    from agents.normalize import normalize_pdf_text
    raw = "\n".join((p.extract_text() or "") for p in PdfReader(SAMPLE / f"{stem}.pdf").pages)
    return normalize_pdf_text(raw)

for label, stem in CALLS.items():
    out_file = OUT / f"{label}.json"
    if out_file.exists():
        print("skip (already built):", label); continue
    try:
        text = load_text(stem)
        res = run_extraction(text, doc_type="auto", doc_id=label)
        d = res.model_dump() if hasattr(res, "model_dump") else res
        h = hedging_stats(text)
        hedging = {"strong_per_1000": h["strong_per_1000"], "evidence": h["strong"][:3]}
        out_file.write_text(json.dumps({"label": label, "extraction": d, "hedging": hedging}, indent=1, default=str))
        print(f"\n== {label}: result keys = {list(d) if isinstance(d, dict) else type(d)}")
        if isinstance(d, dict):
            for m in d.get("metrics") or []:
                print("  metric:", m.get("name"), m.get("basis"), m.get("value"), m.get("unit"), m.get("period"))
            for g in d.get("guidance") or []:
                print("  guidance:", g.get("metric"), g.get("period"), g.get("low"), g.get("high"), g.get("unit"))
        print("  hedging per 1000 words:", hedging["strong_per_1000"])
    except Exception as e:
        print(f"\n== {label}: FAILED -> {type(e).__name__}: {e}")
