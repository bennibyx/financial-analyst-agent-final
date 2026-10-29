
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import api_client

st.set_page_config(page_title="Analysis", page_icon="📈", layout="wide")


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


def show_real_analysis(data):
    """Render the real risk/sentiment API result."""
    st.title("Document Analysis")
    st.caption(
        f"Document ID: {st.session_state.get('analysis_document_id', 'Unknown')} "
        f"· Schema: {data.get('schema_version', 'unknown')}"
    )

    sentiment = data.get("sentiment") or {}
    risk = data.get("risk") or {}
    risks = risk.get("risks") or []
    issues = data.get("issues") or []
    errors = data.get("errors") or {}

    tab_risks, tab_sentiment, tab_issues = st.tabs(
        ["Risks", "Sentiment & Hedging", "Issues & Evidence"]
    )

    with tab_risks:
        level = str(risk.get("overall_risk_level", "unknown")).upper()
        st.subheader(f"Overall risk: {level}")

        if not risk:
            st.warning("The risk agent did not return a result.")
        elif not risks:
            st.info("No verified risks were returned for this document.")
        else:
            for item in risks:
                severity = item.get("severity", "?")
                title = item.get("title", "Untitled risk")
                status = item.get("status", "unknown")
                with st.container(border=True):
                    st.markdown(
                        f"**Severity {severity}/5 · {title}**"
                    )
                    st.caption(
                        f"Category: {item.get('category', 'other')} · "
                        f"Status: {status} · "
                        f"Quantified impact: "
                        f"{'Yes' if item.get('quantified') else 'No'}"
                    )
                    st.write(
                        item.get("explanation")
                        or "No explanation was provided."
                    )
                    quote = item.get("quote")
                    if quote:
                        st.markdown(f"> “{quote}”")

    with tab_sentiment:
        if not sentiment:
            st.warning("The sentiment agent did not return a result.")
        else:
            score = sentiment.get("score")
            overall = sentiment.get("overall", "unknown")
            left, middle, right = st.columns(3)

            left.metric("Management tone", str(overall).title())
            if isinstance(score, (int, float)):
                middle.metric("Sentiment score", f"{score:.2f}")
            else:
                middle.metric("Sentiment score", "Unavailable")

            right.metric(
                "Hedging level",
                str(sentiment.get("hedging_level", "unknown")).title(),
            )

            st.metric(
                "Q&A pushback",
                str(sentiment.get("qa_pushback", "unknown")).title(),
            )

        hedging = data.get("hedging") or {}
        if hedging:
            st.subheader("Measured hedging")
            density = hedging.get("strong_per_1000")
            if isinstance(density, (int, float)):
                st.metric("Strong hedging phrases per 1,000 words",
                          f"{density:.2f}")
            if hedging.get("level"):
                st.caption(f"Measured level: {hedging['level']}")

            for quote in hedging.get("evidence", []):
                st.markdown(f"> “{quote}”")

    with tab_issues:
        if issues:
            st.subheader("Analysis issues")
            for issue in issues:
                st.warning(str(issue))
        else:
            st.success("No analysis issues were reported.")

        if errors:
            st.subheader("Agent errors")
            for agent, message in errors.items():
                st.error(f"{agent}: {message}")

        quotes = sentiment.get("evidence_quotes") or []
        if quotes:
            st.subheader("Sentiment evidence")
            for quote in quotes:
                st.markdown(f"> {quote}")

        with st.expander("Raw analysis response"):
            st.json(data)


# Real analysis results are saved by the Upload page.
real_data = st.session_state.get("analysis")
is_real_analysis = (
    isinstance(real_data, dict)
    and st.session_state.get("analysis_document_id") is not None
)

if is_real_analysis:
    show_real_analysis(real_data)
    st.stop()


# No real analysis selected: retain the existing mock dashboard.
try:
    data = api_client.get_analysis()
except Exception as exc:
    st.error(f"Could not load the sample dashboard: {exc}")
    st.stop()

st.info(
    "Showing sample mock data. Upload and analyze a supported transcript "
    "or CFO commentary to view real results here."
)

st.title(f"{data['company']} · {data['quarter']}")
tab_metrics, tab_risks, tab_sent = st.tabs(
    ["Metrics", "Risks", "Sentiment & Guidance"]
)

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
        for metric in data["metrics"]:
            st.caption(
                f"{metric['name']} (p.{metric['source_page']}): "
                f"“{metric['source_quote']}”"
            )

with tab_risks:
    icons = {"high": "🔴", "medium": "🟠", "low": "🟢"}

    for item in data["risks"]:
        severity = str(item["severity"]).lower()
        with st.container(border=True):
            st.markdown(
                f"**{icons.get(severity, '⚪')} "
                f"{severity.upper()} · {item['title']}**"
            )
            st.write(item["explanation"])
            st.caption(
                f"p.{item['source_page']}: "
                f"“{item['source_quote']}”"
            )

with tab_sent:
    sentiment = data["sentiment"]
    left, right = st.columns(2)

    with left:
        gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sentiment["overall"],
            title={"text": "Overall management tone"},
            gauge={"axis": {"range": [-1, 1]},
                   "bar": {"color": "#0E7C66"}},
        ))
        st.plotly_chart(gauge, use_container_width=True)

    with right:
        frame = pd.DataFrame({
            "Section": ["Prepared remarks", "Q&A"],
            "Sentiment": [
                sentiment["prepared"],
                sentiment["qa"],
            ],
        })
        st.plotly_chart(
            px.bar(
                frame,
                x="Section",
                y="Sentiment",
                range_y=[-1, 1],
                title="Sentiment by section",
            ),
            use_container_width=True,
        )

    st.metric("Hedging phrases", sentiment["hedging_count"])
    guidance = data["guidance"]
    st.subheader("Guidance")
    st.info(
        f"**{guidance['direction'].upper()}** vs prior quarter. "
        f"{guidance['summary']} (p.{guidance['source_page']})"
    )
