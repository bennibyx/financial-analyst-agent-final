import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Sentiment", layout="wide")
st.title("Management tone and sentiment")
st.caption("Mock data for now. This will be replaced by the real extraction API response.")

# Score runs from -1 (very negative) to +1 (very positive).
MOCK_OVERALL = {
    "sentiment": "Positive",
    "score": 0.35,
    "confidence": 0.82,
    "explanation": "Management sounded confident about demand but cautious on supply and export rules.",
}

MOCK_SECTIONS = [
    {"section": "Prepared remarks", "score": 0.62, "sentiment": "Positive", "confidence": 0.90},
    {"section": "Financial results", "score": 0.48, "sentiment": "Positive", "confidence": 0.88},
    {"section": "Outlook / guidance", "score": 0.15, "sentiment": "Neutral",  "confidence": 0.70},
    {"section": "Risk discussion",   "score": -0.40, "sentiment": "Negative", "confidence": 0.78},
    {"section": "Analyst Q&A",       "score": -0.10, "sentiment": "Neutral",  "confidence": 0.65},
]

def label_for(score):
    if score >= 0.2:
        return "Positive"
    if score <= -0.2:
        return "Negative"
    return "Neutral"

def tone_gauge(score, title="Overall tone"):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"valueformat": "+.2f"},
        title={"text": title},
        gauge={
            "axis": {"range": [-1, 1], "tickvals": [-1, -0.5, 0, 0.5, 1]},
            "bar": {"color": "#ecf0f1", "thickness": 0.25},
            "steps": [
                {"range": [-1, -0.2], "color": "#e74c3c"},
                {"range": [-0.2, 0.2], "color": "#f39c12"},
                {"range": [0.2, 1], "color": "#2ecc71"},
            ],
        },
    ))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=60, b=10))
    return fig

def section_chart(sections):
    names = [s["section"] for s in sections]
    scores = [s["score"] for s in sections]
    colors = ["#2ecc71" if x >= 0.2 else "#e74c3c" if x <= -0.2 else "#f39c12" for x in scores]
    hover = [f"{s['sentiment']} (confidence {s['confidence']:.0%})" for s in sections]
    fig = go.Figure(go.Bar(
        x=scores, y=names, orientation="h",
        marker_color=colors,
        text=[f"{x:+.2f}" for x in scores], textposition="outside",
        hovertext=hover, hoverinfo="text+y",
    ))
    fig.update_layout(
        title="Sentiment by section",
        xaxis=dict(range=[-1, 1], zeroline=True, zerolinewidth=2, title="Negative  \u2190  score  \u2192  Positive"),
        yaxis=dict(autorange="reversed"),
        height=360, margin=dict(l=20, r=40, t=60, b=40),
    )
    return fig

def render_sentiment(overall, sections):
    left, right = st.columns([1, 1.4])
    with left:
        st.plotly_chart(tone_gauge(overall["score"]), use_container_width=True)
        st.markdown(f"**{overall['sentiment']}** \u00b7 confidence {overall['confidence']:.0%}")
        st.write(overall["explanation"])
    with right:
        if sections:
            st.plotly_chart(section_chart(sections), use_container_width=True)
        else:
            st.info("No section-level sentiment was found in this document.")

render_sentiment(MOCK_OVERALL, MOCK_SECTIONS)
st.caption("Score runs from -1 (very negative) to +1 (very positive). Green is above +0.2, red is below -0.2.")