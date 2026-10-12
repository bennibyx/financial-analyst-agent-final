"""agents/trends.py - cross-quarter trend insights.
Pure code over saved snapshots (data/trends/<label>.json from scripts/build_snapshots.py).
No model calls: every number is read from an extraction or computed here.
Run: python3 -m agents.trends"""
import json, pathlib, re
from statistics import mean
from .guidance_compare import compare_guidance

SCHEMA_VERSION = "1.0"
ORDER = ["Q4FY26", "Q1FY27", "Q2FY27"]
SERIES = [("revenue", None), ("gross_margin", "GAAP"), ("gross_margin", "non-GAAP"), ("free_cash_flow", None)]


def load_snapshots(folder="data/trends", labels=ORDER):
    out = []
    for label in labels:
        p = pathlib.Path(folder) / f"{label}.json"
        if p.exists():
            out.append(json.loads(p.read_text()))
    return out


def _pick(metrics, name, basis):
    rows = [m for m in metrics if m.get("name") == name and m.get("basis") == basis and m.get("value") is not None]
    return rows[0] if rows else None


def _val(m):
    """Value in USD millions (or percent)."""
    if not m:
        return None
    return m["value"] * 1000 if m.get("unit") == "USD_billion" else m["value"]


def _band(quote):
    """'plus or minus 2%' in a guidance quote -> 2.0"""
    m = re.search(r"plus or minus\s+(\d+(?:\.\d+)?)\s*%", quote or "", re.I)
    return float(m.group(1)) if m else None


def metric_series(snaps):
    """Headline metrics per quarter with QoQ change (percent for amounts, points for margins)."""
    out = []
    for name, basis in SERIES:
        is_pct = name == "gross_margin"
        points, prev = [], None
        for s in snaps:
            m = _pick(s["extraction"].get("metrics", []), name, basis)
            val = _val(m)
            change = None
            if val is not None and prev is not None:
                change = round(val - prev, 2) if is_pct else round((val / prev - 1) * 100, 2)
            points.append({"quarter": s["label"], "value": val,
                           "status": "reported" if m else "not_reported",
                           "qoq_change": change, "qoq_unit": "pts" if is_pct else "%",
                           "yoy_pct_stated": m.get("yoy_change_pct") if m else None,
                           "source_quote": (m.get("source_quote") or "")[:160] if m else None})
            prev = val
        out.append({"metric": name, "basis": basis, "unit": "percent" if is_pct else "USD_million", "points": points})
    return out


def guidance_track(snaps):
    """For each consecutive pair: what was guided last call vs what was reported. Only same-period comparisons count."""
    pairs = []
    for prior, later in zip(snaps, snaps[1:]):
        rows = compare_guidance(prior["extraction"], later["extraction"])
        seen, compared, skipped = set(), [], []
        for r in rows:
            key = (r["metric"], r.get("basis"), r.get("guided_period"))
            if key in seen:                                   # extraction sometimes repeats a row
                continue
            seen.add(key)
            if r.get("verdict") == "no_match":
                skipped.append({"metric": r["metric"], "basis": r.get("basis"), "guided_period": r.get("guided_period"),
                                "reason": "no matching reported value"})
            elif not r.get("period_match"):
                skipped.append({"metric": r["metric"], "basis": r.get("basis"), "guided_period": r.get("guided_period"),
                                "reason": "guided period differs from the reported period (e.g. full-year guidance)"})
            else:
                r = dict(r)
                r["band_pct"] = _band(r.get("guided_quote"))
                r["beyond_band"] = bool(r["band_pct"] is not None and r.get("diff_unit") == "%" and abs(r["diff"]) > r["band_pct"])
                compared.append(r)
        pairs.append({"guided_on": prior["label"], "reported_on": later["label"], "compared": compared, "skipped": skipped})
    verdicts = [r["verdict"] for p in pairs for r in p["compared"]]
    rev = [r["diff"] for p in pairs for r in p["compared"] if r["metric"] == "revenue" and r.get("diff_unit") == "%"]
    summary = {"compared": len(verdicts), "above": verdicts.count("above"), "in_line": verdicts.count("in_line"),
               "below": verdicts.count("below"), "revenue_beats_n": len(rev),
               "revenue_avg_beat_pct": round(mean(rev), 2) if rev else None}
    return {"pairs": pairs, "summary": summary}


def tone_trend(snaps):
    pts = [{"quarter": s["label"], "strong_hedges_per_1000": s["hedging"]["strong_per_1000"],
            "evidence": s["hedging"].get("evidence", [])} for s in snaps if s.get("hedging")]
    direction = None
    if len(pts) >= 2:
        d = pts[-1]["strong_hedges_per_1000"] - pts[0]["strong_hedges_per_1000"]
        direction = "flat" if abs(d) < 0.05 else ("less_hedging" if d < 0 else "more_hedging")
    return {"points": pts, "direction": direction,
            "note": "code-measured density of strong hedging phrases; counts are small, so directional only"}


def outlook(snaps, beat):
    """Guidance-implied outlook from the latest call. NOT a forecast."""
    latest = snaps[-1]
    ex = latest["extraction"]
    out = {"based_on": latest["label"], "type": "guidance-implied outlook (not a forecast)"}
    is_q = lambda g: str(g.get("period", "")).upper().startswith("Q")
    actual_rev = _pick(ex["metrics"], "revenue", None)
    g_rev = next((g for g in ex["guidance"] if g["metric"] == "revenue" and g.get("midpoint") is not None and is_q(g)), None)
    if g_rev and actual_rev:
        mid = g_rev["midpoint"] * 1000 if g_rev.get("unit") == "USD_billion" else g_rev["midpoint"]
        band = _band(g_rev.get("source_quote"))
        out["revenue"] = {
            "period": g_rev["period"], "guided_midpoint_musd": mid, "band_pct": band,
            "range_musd": [round(mid * (1 - band / 100)), round(mid * (1 + band / 100))] if band else None,
            "implied_qoq_pct": round((mid / _val(actual_rev) - 1) * 100, 2),
            "illustrative_if_past_beats_repeat_musd":
                round(mid * (1 + beat["avg"] / 100)) if beat.get("avg") is not None else None,
            "illustrative_note": f"average revenue beat of {beat.get('avg')}% over {beat.get('n')} guided quarters; small sample, NOT a prediction"}
    actual_gm = _pick(ex["metrics"], "gross_margin", "GAAP")
    g_gm = next((g for g in ex["guidance"] if g["metric"] == "gross_margin" and g.get("basis") == "GAAP"
                 and g.get("midpoint") is not None and is_q(g)), None)
    if g_gm and actual_gm:
        out["gross_margin"] = {"period": g_gm["period"], "guided_pct": g_gm["midpoint"],
                               "implied_change_pts": round(g_gm["midpoint"] - actual_gm["value"], 2)}
    return out


def build_trends(snaps=None):
    snaps = snaps or load_snapshots()
    if not snaps:
        raise ValueError("no snapshots found: run python3 scripts/build_snapshots.py")
    series = metric_series(snaps)
    track = guidance_track(snaps)
    s = track["summary"]
    notes = [f"{x['metric']} {x['basis'] or ''} not reported for {p['quarter']}".replace("  ", " ")
             for x in series for p in x["points"] if p["status"] == "not_reported"]
    notes += ["QoQ change is computed by code; YoY appears only where the call states it.",
              "Only same-period guidance is compared; full-year guidance is skipped.",
              "Outlook is implied by management guidance, not a forecast."]
    return {"schema_version": SCHEMA_VERSION, "quarters": [x["label"] for x in snaps], "series": series,
            "guidance_track": track, "tone": tone_trend(snaps),
            "outlook": outlook(snaps, {"avg": s["revenue_avg_beat_pct"], "n": s["revenue_beats_n"]}),
            "data_notes": notes}


if __name__ == "__main__":
    print(json.dumps(build_trends(), indent=1))
