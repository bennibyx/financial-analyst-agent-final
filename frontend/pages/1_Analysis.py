import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import api_client

st.set_page_config(page_title="Analysis", page_icon="📈", layout="wide")

data = st.session_state.get("analysis")
if data is None:
    data = api_client.get_analysis()
    st.info("Showing sample mock data. Run an analysis on the Upload page to replace it.")

st.title(f"{data['company']} · {data['quarter']}")
tab_metrics, tab_risks, tab_sent = st.tabs(["Metrics", "Risks", "Sentiment & Guidance"])


def fmt_value(v, unit):
    """Turn a raw number into a readable string."""
    if unit == "%":
        return f"{v:.1f}%"
    if unit == "USD":
        if abs(v) >= 1e9:
            return f"${v / 1e9:.2f}B"
        if abs(v) >= 1e6:
            return f"${v / 1e6:.1f}M"
        return f"${v:,.2f}"
    return f"{v:,}"


with tab_metrics:
    rows = [{
        "Metric": m["name"],
        "Value": fmt_value(m["value"], m["unit"]),
        "QoQ": f"{m['qoq_pct']:+.1f}%",
        "YoY": f"{m['yoy_pct']:+.1f}%",
        "Source": f"p.{m['source_page']}",
    } for m in data["metrics"]]
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    with st.expander("Source quotes"):
        for m in data["metrics"]:
            st.caption(f"{m['name']} (p.{m['source_page']}): “{m['source_quote']}”")

with tab_risks:
    icon = {"high": "🔴", "medium": "🟠", "low": "🟢"}
    for r in data["risks"]:
        with st.container(border=True):
            st.markdown(f"**{icon[r['severity']]} {r['severity'].upper()} · {r['title']}**")
            st.write(r["explanation"])
            st.caption(f"p.{r['source_page']}: “{r['source_quote']}”")

with tab_sent:
    s = data["sentiment"]
    left, right = st.columns(2)
    with left:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number", value=s["overall"],
            title={"text": "Overall management tone"},
            gauge={"axis": {"range": [-1, 1]}, "bar": {"color": "#0E7C66"}},
        ))
        st.plotly_chart(gauge)
    with right:
        df = pd.DataFrame({"Section": ["Prepared remarks", "Q&A"],
                           "Sentiment": [s["prepared"], s["qa"]]})
        st.plotly_chart(px.bar(df, x="Section", y="Sentiment", range_y=[-1, 1],
                               title="Sentiment by section"))
    st.metric("Hedging phrases", s["hedging_count"])
    g = data["guidance"]
    st.subheader("Guidance")
    st.info(f"**{g['direction'].upper()}** vs prior quarter. {g['summary']} (p.{g['source_page']})")