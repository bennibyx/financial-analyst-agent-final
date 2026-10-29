import streamlit as st
import pandas as pd

st.set_page_config(page_title="Financial Metrics", layout="wide")
st.title("Financial metrics")
st.caption("Mock data for now. This will be replaced by the real extraction API response.")

# Mock data. None means the value is missing.
MOCK = [
    {"metric": "Revenue",         "unit": "USD_B", "current": 85.8, "prev_q": 94.8, "prev_y": 81.8},
    {"metric": "Net income",      "unit": "USD_B", "current": 21.4, "prev_q": 24.2, "prev_y": 19.9},
    {"metric": "EPS (diluted)",   "unit": "USD",   "current": 1.26, "prev_q": 1.53, "prev_y": 1.26},
    {"metric": "Gross margin",    "unit": "%",     "current": 46.3, "prev_q": 46.6, "prev_y": 44.5},
    {"metric": "Operating margin","unit": "%",     "current": 29.0, "prev_q": 30.1, "prev_y": 27.4},
    {"metric": "Free cash flow",  "unit": "USD_B", "current": 26.7, "prev_q": None, "prev_y": 24.0},
]

def fmt_value(v, unit):
    if v is None:
        return "—"
    if unit == "USD_B":
        return f"${v:,.1f}B"
    if unit == "USD":
        return f"${v:,.2f}"
    if unit == "%":
        return f"{v:.1f}%"
    return f"{v:,.2f}"

def change(cur, old, unit):
    """Percent change, or percentage points for margin rows."""
    if cur is None or old is None:
        return None
    if unit == "%":
        return cur - old
    if old == 0:
        return None
    return (cur - old) / abs(old) * 100

def fmt_change(x, unit):
    if x is None:
        return "—"
    arrow = "▲" if x > 0 else "▼" if x < 0 else "–"
    suffix = " pp" if unit == "%" else "%"
    return f"{arrow} {abs(x):.1f}{suffix}"

def color_change(val):
    if isinstance(val, str) and val.startswith("▲"):
        return "color: #2ecc71; font-weight: 600"
    if isinstance(val, str) and val.startswith("▼"):
        return "color: #e74c3c; font-weight: 600"
    return ""

def render_metrics_table(rows):
    table = []
    for r in rows:
        u = r["unit"]
        table.append({
            "Metric": r["metric"],
            "Current": fmt_value(r["current"], u),
            "Prev quarter": fmt_value(r["prev_q"], u),
            "Prev year": fmt_value(r["prev_y"], u),
            "QoQ": fmt_change(change(r["current"], r["prev_q"], u), u),
            "YoY": fmt_change(change(r["current"], r["prev_y"], u), u),
        })
    df = pd.DataFrame(table)
    styler = df.style
    apply_fn = styler.map if hasattr(styler, "map") else styler.applymap
    styled = apply_fn(color_change, subset=["QoQ", "YoY"])
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False), "metrics.csv", "text/csv")
render_metrics_table(MOCK)
st.caption("pp = percentage points. — means the value was not found in the document.")