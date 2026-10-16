# Day 20: benchmark models on the SAME extraction answer keys.
# Run from repo root:  python3 -m scripts.benchmark_models [model_id ...]
# No arguments = the default shortlist. Skips doc5 (PDF copy of doc4) to save credits.
import os, sys, io, json, time, pathlib, datetime, contextlib
import agents.llm as L
from agents.extraction_agent import run_extraction
from agents.verify import clean_text
from scripts.eval_extraction import GT_DIR, NOT_IN_SCHEMA, score_row, squash

DEFAULT_MODELS = [
    "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B",     # current model (baseline)
    "nvidia/nemotron-3-super-120b-a12b",
    "nvidia/Nemotron-3_5-Lightning",
    "Qwen/Qwen3-30B-A3B-Instruct-2507",
    "openai/gpt-oss-120b",
]
SKIP_DOCS = {"doc5"}

# Per-call time limit so one slow model cannot block the whole run (BENCH_TIMEOUT seconds, default 120).
L.client = L.client.with_options(timeout=float(os.environ.get('BENCH_TIMEOUT', '120')), max_retries=0)

# Count calls and tokens by wrapping the API call.
stats = {"calls": 0, "prompt": 0, "completion": 0}
_orig_create = L.client.chat.completions.create
def _counted(*a, **k):
    r = _orig_create(*a, **k)
    stats["calls"] += 1
    u = getattr(r, "usage", None)
    if u:
        stats["prompt"] += getattr(u, "prompt_tokens", 0) or 0
        stats["completion"] += getattr(u, "completion_tokens", 0) or 0
    return r
L.client.chat.completions.create = _counted

def run_model(model):
    L.MODEL = model
    # The enable_thinking flag is Nemotron-specific: only send it to NVIDIA models.
    L.THINKING = not model.startswith("nvidia/")
    for k in stats: stats[k] = 0
    res = {"model": model, "correct": 0, "wrong": 0, "missing": 0, "hallucinated": 0,
           "crashed": 0, "total": 0, "retries": 0, "errors": []}
    t0 = time.time()
    for path in sorted(GT_DIR.glob("*.json")):
        gt = json.loads(path.read_text())
        if gt["doc_id"] in SKIP_DOCS:
            continue
        names = [n for n in gt["metrics"] if n not in NOT_IN_SCHEMA]
        raw = pathlib.Path(gt["source_file"]).read_text(errors="ignore")
        try:
            if os.environ.get("BENCH_VERBOSE"):                  # show agent logging
                out = run_extraction(raw, doc_id=gt["doc_id"])
            else:
                with contextlib.redirect_stdout(io.StringIO()):  # silence agent logging
                    out = run_extraction(raw, doc_id=gt["doc_id"])
        except Exception as e:
            res["crashed"] += len(names); res["total"] += len(names)
            res["errors"].append(f"{gt['doc_id']}: {str(e)[:150]}")
            continue
        r = out.get("retries")
        if isinstance(r, int): res["retries"] += r
        text_sq = squash(clean_text(raw))
        for name in names:
            status, _, _ = score_row(name, gt["metrics"][name], out, text_sq)
            res["total"] += 1
            if status in ("CORRECT", "OK_NULL"): res["correct"] += 1
            elif status == "WRONG": res["wrong"] += 1
            elif status == "MISSING": res["missing"] += 1
            elif status == "HALLUCINATED": res["hallucinated"] += 1
    res["seconds"] = round(time.time() - t0, 1)
    res.update(calls=stats["calls"], prompt_tokens=stats["prompt"], completion_tokens=stats["completion"])
    return res

def main():
    models = sys.argv[1:] or DEFAULT_MODELS
    results = []
    for m in models:
        print(f"\n>>> {m}", flush=True)
        r = run_model(m)
        results.append(r)
        print(f"    {r['correct']}/{r['total']} correct | wrong {r['wrong']} missing {r['missing']} "
              f"halluc {r['hallucinated']} crashed {r['crashed']} | {r['seconds']}s | "
              f"{r['calls']} calls | tokens in/out {r['prompt_tokens']}/{r['completion_tokens']}", flush=True)
        for e in r["errors"][:2]: print("    error:", e)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    pathlib.Path("docs/benchmark_runs").mkdir(exist_ok=True)
    pathlib.Path(f"docs/benchmark_runs/benchmark_{ts}.json").write_text(json.dumps(results, indent=2))
    lines = ["| Model | Correct | Wrong / Missing / Halluc. | Crashed | Time (s) | Calls | Tokens in / out |",
             "|---|---|---|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r['model']} | {r['correct']}/{r['total']} | {r['wrong']} / {r['missing']} / {r['hallucinated']} "
                     f"| {r['crashed']} | {r['seconds']} | {r['calls']} | {r['prompt_tokens']} / {r['completion_tokens']} |")
    print("\n" + "\n".join(lines))
    pathlib.Path(f"docs/benchmark_runs/benchmark_{ts}.md").write_text("\n".join(lines) + "\n")
    print(f"\nsaved docs/benchmark_runs/benchmark_{ts}.json and .md")

if __name__ == "__main__":
    main()
