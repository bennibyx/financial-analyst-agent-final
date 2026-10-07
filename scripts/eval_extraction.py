# Scores the Extraction Agent against the hand-made answer keys.
# Run from repo root:  python3 -m scripts.eval_extraction
import json, re, pathlib, datetime
from agents.extraction_agent import run_extraction
from agents.verify import clean_text

GT_DIR = pathlib.Path("agents/eval/ground_truth")
NAME_MAP = {"eps_diluted": "eps"}         # answer-key name -> schema name
NOT_IN_SCHEMA = {"operating_income"}      # agent cannot output these yet
TOL = 0.005                               # 0.5% relative tolerance

def squash(s):
    return re.sub(r"\s+", " ", s or "").strip().lower()

def to_base(value, unit):
    """Money in billions -> millions so units compare fairly."""
    if value is None:
        return None
    return value * 1000 if (unit or "").lower() in ("usd_billion", "usd_billions") else value

def close(pred, truth, unit):
    if unit == "percent":
        return abs(pred - truth) <= 0.05
    return abs(pred - truth) <= TOL * abs(truth)

def candidates(out, name):
    """All agent rows that could be the answer for this metric."""
    if name == "guidance_revenue_next_quarter":
        rows = []
        for g in out["guidance"]:
            if "revenue" not in g["metric"].lower():
                continue
            v = g.get("midpoint")
            if v is None and g.get("low") is not None and g.get("high") is not None:
                v = (g["low"] + g["high"]) / 2
            rows.append({"value": v, "unit": g["unit"], "basis": g.get("basis"),
                         "quote": g["source_quote"], "period": g["period"]})
        return rows
    wanted = NAME_MAP.get(name, name)
    return [{"value": m["value"], "unit": m["unit"], "basis": m.get("basis"),
             "quote": m["source_quote"], "period": m["period"]}
            for m in out["metrics"] if m["name"] == wanted]

def is_grounded(row, text_sq):
    return bool(row and row["quote"] and squash(row["quote"]) in text_sq)

def score_row(name, truth, out, text_sq):
    if name in NOT_IN_SCHEMA:
        return "NOT_IN_SCHEMA", None, None
    cands = candidates(out, name)
    want = truth.get("basis")
    if want:
        cands = [c for c in cands if c["basis"] in (want, None)] or cands
    with_val = [c for c in cands if c["value"] is not None]
    if truth["value"] is None:                       # a "not stated" test
        if with_val:
            return "HALLUCINATED", with_val[0], is_grounded(with_val[0], text_sq)
        return "OK_NULL", None, None
    if not with_val:
        return "MISSING", None, None
    for c in with_val:
        if close(to_base(c["value"], c["unit"]), to_base(truth["value"], truth["unit"]), truth["unit"]):
            return "CORRECT", c, is_grounded(c, text_sq)
    return "WRONG", with_val[0], is_grounded(with_val[0], text_sq)

def main():
    report, all_status, grounded_flags = {}, [], []
    for path in sorted(GT_DIR.glob("*.json")):
        gt = json.loads(path.read_text())
        raw = pathlib.Path(gt["source_file"]).read_text(errors="ignore")
        print(f"\n== {gt['doc_id']} ({gt['source_file']}) ==  running agent...", flush=True)
        try:
            out = run_extraction(raw, doc_id=gt["doc_id"])
        except Exception as e:
            print(f"  AGENT CRASHED: {e}")
            report[gt["doc_id"]] = {"crashed": str(e)}
            all_status += ["CRASHED"] * sum(1 for n in gt["metrics"] if n not in NOT_IN_SCHEMA)
            continue
        text_sq = squash(clean_text(raw))
        rows = []
        for name, truth in gt["metrics"].items():
            status, pred, grounded = score_row(name, truth, out, text_sq)
            pv = pred["value"] if pred else None
            pu = pred["unit"] if pred else ""
            print(f"{name:<32}{status:<15}truth={truth['value']}  pred={pv} {pu}  grounded={grounded}")
            rows.append({"metric": name, "status": status, "truth": truth["value"],
                         "pred": pred, "grounded": grounded})
            if status != "NOT_IN_SCHEMA":
                all_status.append(status)
            if grounded is not None:
                grounded_flags.append(grounded)
        print(f"agent issues: {out['issues']}")
        report[gt["doc_id"]] = {"rows": rows, "issues": out["issues"], "retries": out["retries"]}
    good = sum(s in ("CORRECT", "OK_NULL") for s in all_status)
    print(f"\nACCURACY {good}/{len(all_status)} = {good/len(all_status):.0%}")
    print(f"HALLUCINATED (invented values): {all_status.count('HALLUCINATED')}")
    print(f"WRONG: {all_status.count('WRONG')} | MISSING: {all_status.count('MISSING')}")
    if grounded_flags:
        print(f"QUOTES FOUND IN SOURCE: {sum(grounded_flags)}/{len(grounded_flags)}")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out_path = pathlib.Path("docs/eval_runs") / f"extraction_{stamp}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"saved {out_path}")

if __name__ == "__main__":
    main()
