import os

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Financial Metrics", layout="wide")
st.title("Financial metrics")

# Same env var the other pages use; defaults to a local backend.
API = os.getenv("FINANCIAL_ANALYST_API_URL", "http://127.0.0.1:8000").rstrip("/")
st.caption(f"Live data from {API}. Extraction calls the model, so a first run can take a minute or two.")

LABELS = {"eps": "EPS", "free_cash_flow": "Free cash flow"}


def label(name):
    return LABELS.get(name, name.replace("_", " ").capitalize())


def fmt_value(v, unit):
    if v is None:
        return "—"
    if unit == "USD_million":
        return f"${v / 1000:,.2f}B" if abs(v) >= 1000 else f"${v:,.0f}M"
    if unit == "USD_billion":
        return f"${v:,.2f}B"
    if unit == "USD":
        return f"${v:,.2f}"
    if unit == "percent":
        return f"{v:.1f}%"
    return f"{v:,.2f} {unit}"


def fmt_change(x):
    if x is None:
        return "—"
    arrow = "▲" if x > 0 else "▼" if x < 0 else "–"
    return f"{arrow} {abs(x):.1f}%"


def color_change(val):
    if isinstance(val, str) and val.startswith("▲"):
        return "color: #2ecc71; font-weight: 600"
    if isinstance(val, str) and val.startswith("▼"):
        return "color: #e74c3c; font-weight: 600"
    return ""


def fetch_extract(doc_id):
    url = f"{API}/extract/{doc_id}"
    r = requests.post(url, timeout=130)
    if r.status_code == 405:  # endpoint may be GET instead of POST
        r = requests.get(url, timeout=130)
    r.raise_for_status()
    return r.json()


def show(result):
    data = result["data"]
    metrics = data.get("metrics") or []
    head = " · ".join(str(x) for x in (data.get("company"), data.get("period"), data.get("doc_type")) if x)
    st.subheader(head or f"Document {result['doc_id']}")
    if data.get("stub"):
        st.warning("This is fake sample data (stub), not a real extraction.")
    if not metrics:
        st.info("No metrics could be extracted from this document.")
        return

    rows = []
    for m in metrics:
        rows.append({
            "Metric": label(m.get("name", "unknown")),
            "Basis": m.get("basis") or "—",
            "Period": m.get("period") or "—",
            "Value": fmt_value(m.get("value"), m.get("unit")),
            "QoQ": fmt_change(m.get("qoq_change_pct")),
            "YoY": fmt_change(m.get("yoy_change_pct")),
        })
    df = pd.DataFrame(rows)
    styler = df.style
    apply_fn = styler.map if hasattr(styler, "map") else styler.applymap
    st.dataframe(apply_fn(color_change, subset=["QoQ", "YoY"]), use_container_width=True, hide_index=True)
    st.download_button("Download CSV", df.to_csv(index=False), "metrics.csv", "text/csv")

    missing = [r["Metric"] for r in rows if r["Value"] == "—"]
    if missing:
        st.warning("Not found in this document: " + ", ".join(missing))

    with st.expander("Source quotes", expanded=True):
        for m in metrics:
            q = (m.get("source_quote") or "").replace("$", "\\$")
            name = label(m.get("name", "unknown"))
            st.markdown(f"**{name}**: “{q}”" if q else f"**{name}**: no source quote")

    issues = data.get("issues") or []
    if issues:
        with st.expander(f"Extraction notes ({len(issues)})"):
            for i in issues:
                st.write("- " + str(i))

    st.caption("— means the value was not found in the document. QoQ/YoY are only shown when the document states them.")


doc_id = st.number_input("Document ID", min_value=1, value=1, step=1)

if st.button("Extract metrics", type="primary"):
    with st.spinner("Extracting metrics..."):
        try:
            st.session_state["metrics_result"] = {"doc_id": int(doc_id), "data": fetch_extract(int(doc_id))}
        except requests.Timeout:
            st.session_state.pop("metrics_result", None)
            st.error("Timed out. The server may be waking up (free tier). Click the button again.")
        except requests.ConnectionError:
            st.session_state.pop("metrics_result", None)
            st.error(f"Cannot reach {API}. Check that the backend is running and the URL is right.")
        except requests.HTTPError as e:
            st.session_state.pop("metrics_result", None)
            st.error(f"Backend returned {e.response.status_code}: {e.response.text[:300]}")

if "metrics_result" in st.session_state:
    show(st.session_state["metrics_result"])
