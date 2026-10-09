# agents/guidance_compare.py -- compare what management guided last call with what the next call reported
import re

COMPARABLE = {"revenue": "pct", "gross_margin": "points"}   # the only names present in BOTH guidance and reported metrics

def _to_millions(value, unit):
    if value is None:
        return None
    return value * 1000 if unit == "USD_billion" else value    # USD_million and percent stay as they are

def _period_key(p):
    """'Q1 2027', 'Q1 FY2027' and 'Q1 FY27' all become ('Q1', '27')."""
    p = p or ""
    q = re.search(r"Q([1-4])", p, re.I)
    y = re.search(r"(20)?(\d\d)\b", re.sub(r"Q[1-4]", "", p, flags=re.I))
    return ("Q" + q.group(1) if q else None, y.group(2) if y else None)

def _guided_value(g):
    if g.get("midpoint") is not None:
        return g["midpoint"]
    if g.get("low") is not None and g.get("high") is not None:
        return (g["low"] + g["high"]) / 2
    return None

def _pick_actual(metrics, name, basis):
    rows = [m for m in metrics if m["name"] == name and m.get("value") is not None]
    if basis:
        same = [m for m in rows if m.get("basis") == basis]
        if same:
            return same[0]
    no_basis = [m for m in rows if m.get("basis") is None]
    return (no_basis or rows or [None])[0]

def compare_guidance(prior, later, tol_pct=1.0, tol_points=0.5):
    """prior/later: {"metrics": [...], "guidance": [...]} as returned by run_extraction.
    Returns one row per guided metric: guided vs reported, with a verdict."""
    out = []
    for g in prior.get("guidance", []):
        name = g["metric"]
        if name not in COMPARABLE:
            continue
        guided = _guided_value(g)
        a = _pick_actual(later.get("metrics", []), name, g.get("basis"))
        row = {"metric": name, "basis": g.get("basis"), "guided_period": g["period"],
               "guided_quote": (g.get("source_quote") or "")[:160]}
        if guided is None or a is None:
            row["verdict"] = "no_match"
            out.append(row)
            continue
        gv, av = _to_millions(guided, g["unit"]), _to_millions(a["value"], a["unit"])
        if COMPARABLE[name] == "pct":
            diff, tol, unit = (av - gv) / gv * 100, tol_pct, "%"
        else:
            diff, tol, unit = av - gv, tol_points, " pts"
        row.update({"guided": guided, "guided_unit": g["unit"], "actual": a["value"], "actual_unit": a["unit"],
                    "actual_basis": a.get("basis"), "actual_period": a["period"],
                    "period_match": _period_key(g["period"]) == _period_key(a["period"]),
                    "diff": round(diff, 2), "diff_unit": unit,
                    "verdict": "above" if diff > tol else ("below" if diff < -tol else "in_line"),
                    "actual_quote": (a.get("source_quote") or "")[:160]})
        out.append(row)
    return out
