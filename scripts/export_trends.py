"""Run: python3 scripts/export_trends.py - writes backend/app/trends.json (numbers only, no transcript quotes)"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from agents.trends import build_trends

DROP = {"source_quote", "guided_quote", "actual_quote", "evidence"}   # keys that hold transcript text

def strip(x):
    if isinstance(x, dict):
        return {k: strip(v) for k, v in x.items() if k not in DROP}
    if isinstance(x, list):
        return [strip(v) for v in x]
    return x

out = pathlib.Path("backend/app/trends.json")
out.write_text(json.dumps(strip(build_trends()), indent=1))
print("wrote", out, out.stat().st_size, "bytes")
