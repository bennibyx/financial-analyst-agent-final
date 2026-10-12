"""agents/brief.py - one-page analyst brief (JSON + Markdown) from an orchestrator result.
Pure code over verified agent outputs: no model calls, nothing is invented here."""
import re

SCHEMA_VERSION = "1.0"


def _fmt(v, unit):
    if v is None:
        return "n/a"
    if unit == "USD_million":
        return f"${v / 1000:.1f}B" if abs(v) >= 1000 else f"${v:g}M"
    if unit == "USD_billion":
        return f"${v:g}B"
    if unit == "percent":
        return f"{v:g}%"
    if unit == "USD":
        return f"${v:g}"
    return f"{v:g} {unit}" if unit else f"{v:g}"


def _dedup(rows, key):
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _guided_display(g):
    unit = g.get("unit")
    if g.get("midpoint") is not None:
        s = _fmt(g["midpoint"], unit)
        if g.get("range_pct") is not None:
            s += f" (+/- {g['range_pct']:g} pts)" if unit == "percent" else f" (+/- {g['range_pct']:g}%)"
        return s
    if g.get("low") is not None and g.get("high") is not None:
        return f"{_fmt(g['low'], unit)} to {_fmt(g['high'], unit)}"
    return g.get("qualitative")                       # may be None -> row is skipped


def _clip(text, n=240):
    text = (text or "").strip()
    return text if len(text) <= n else text[:n].rstrip() + "..."


def _kept(d):
    return d.get("kept") if isinstance(d, dict) and d.get("kept") is not None else "n/a"


def _strip_label(q):
    return re.sub(r"^[A-Z]+:\s*", "", q or "")


def build_brief(orch):
    res = orch.get("results") or {}
    ex, an = res.get("extract") or {}, res.get("analyze") or {}
    metrics = _dedup(ex.get("metrics") or [], lambda m: (m["name"], m.get("basis"), m.get("period")))
    period = next((m.get("period") for m in metrics if m.get("period")), None)

    m_rows = [{"name": m["name"], "basis": m.get("basis"), "period": m.get("period"),
               "value": m.get("value"), "unit": m.get("unit"), "display": _fmt(m.get("value"), m.get("unit")),
               "yoy_change_pct": m.get("yoy_change_pct"), "source_quote": m.get("source_quote")} for m in metrics]

    g_rows = []
    for g in ex.get("guidance") or []:
        disp = _guided_display(g)
        if disp:
            g_rows.append({"metric": g["metric"], "basis": g.get("basis"), "period": g.get("period"),
                           "display": disp, "source_quote": g.get("source_quote")})
    g_rows = _dedup(g_rows, lambda g: (g["metric"], g["basis"], g["period"], g["display"]))

    sent, risk, hedge = an.get("sentiment") or {}, an.get("risk") or {}, an.get("hedging") or {}
    risks = sorted(risk.get("risks") or [], key=lambda r: -(r.get("severity") or 0))[:5]
    r_rows = [{"category": r.get("category"), "title": r.get("title"), "severity": r.get("severity"),
               "status": r.get("status"), "quote": r.get("quote"), "explanation": r.get("explanation")} for r in risks]

    ev = sent.get("evidence_quotes") or []
    tone_q = [_clip(_strip_label(q)) for q in ev if q.startswith("TONE:")][:2]
    push_q = [_clip(_strip_label(q)) for q in ev if q.startswith("PUSHBACK:")][:1]

    brief = {
        "schema_version": SCHEMA_VERSION, "doc_id": orch.get("doc_id"),
        "doc_type": ex.get("doc_type"), "period": period,
        "headline": {"overall_sentiment": sent.get("overall"), "sentiment_score": sent.get("score"),
                     "risk_level": risk.get("overall_risk_level"), "hedging_level": hedge.get("level")},
        "metrics": m_rows, "guidance": g_rows,
        "tone": {"qa_pushback": sent.get("qa_pushback"),
                 "hedging": {"level": hedge.get("level"), "strong_per_1000": hedge.get("strong_per_1000"),
                             "evidence": [_clip(q) for q in (hedge.get("evidence") or [])]},
                 "management_tone_quotes": tone_q, "analyst_pushback_quotes": push_q},
        "risks": r_rows,
        "verification": {"agent_errors": an.get("errors") or {}, "agent_issue_count": len(an.get("issues") or []),
                         "sentiment_quotes": an.get("sentiment_quotes"), "risk_quotes": an.get("risk_quotes"),
                         "analysis_truncated_to_chars": (orch.get("checks") or {}).get("analyze_truncated_to_chars")},
    }
    brief["markdown"] = to_markdown(brief)
    return brief


def to_markdown(b):
    h, t = b["headline"], b["tone"]
    L = [f"# Analyst Brief: {b.get('doc_type') or 'document'} {b.get('period') or ''}".strip(), ""]
    if h["overall_sentiment"] or h["risk_level"]:
        L += ["| Overall sentiment | Risk level | Hedging (measured) |", "|---|---|---|",
              f"| {h['overall_sentiment'] or 'n/a'} ({h['sentiment_score']}) | {h['risk_level'] or 'n/a'} | {h['hedging_level'] or 'n/a'} |", ""]
    L += ["## Headline metrics", ""]
    if b["metrics"]:
        L += ["| Metric | Basis | Value | Period |", "|---|---|---|---|"]
        L += [f"| {m['name']} | {m['basis'] or '-'} | {m['display']} | {m['period'] or '-'} |" for m in b["metrics"]]
    else:
        L += ["_Not available for this document._"]
    L += ["", "## Management guidance", ""]
    if b["guidance"]:
        L += ["| Metric | Basis | Period | Guided |", "|---|---|---|---|"]
        L += [f"| {g['metric']} | {g['basis'] or '-'} | {g['period']} | {g['display']} |" for g in b["guidance"]]
    else:
        L += ["_Not available for this document._"]
    L += ["", "## Tone and language", ""]
    if h["overall_sentiment"]:
        L += [f"- Q&A pushback: **{t['qa_pushback']}**",
              f"- Strong hedging phrases: **{t['hedging']['strong_per_1000']} per 1000 words** ({t['hedging']['level']}), counted by code"]
        L += [f"- Management tone: \"{q}\"" for q in t["management_tone_quotes"]]
        L += [f"- Analyst pushback: \"{q}\"" for q in t["analyst_pushback_quotes"]]
        L += [f"- Hedging example: \"{q}\"" for q in t["hedging"]["evidence"][:2]]
    else:
        L += ["_Not available for this document._"]
    L += ["", "## Top risks", ""]
    if b["risks"]:
        for r in b["risks"]:
            L += [f"**{r['title']}** ({r['category']}, severity {r['severity']}/5, {r['status']})",
                  f"> \"{r['quote']}\"", f"{r['explanation']}", ""]
    else:
        L += ["_Not available for this document._", ""]
    v = b["verification"]
    L += ["## Verification notes", "",
          f"- Quotes are checked against the source text by the agents (risk quotes kept: {_kept(v['risk_quotes'])}, sentiment quotes kept: {_kept(v['sentiment_quotes'])}).",
          f"- Agent errors: {v['agent_errors'] or 'none'}.",
          "- This brief is assembled by code from those verified outputs; it adds no new claims."]
    return "\n".join(L)
