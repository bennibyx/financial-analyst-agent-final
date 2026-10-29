
import streamlit as st

st.set_page_config(page_title="Risk Highlights", layout="wide")
st.title("Risk highlights")
st.caption("Risk highlights from the latest real analysis.")

# Mock risk data
MOCK_RISKS = [
    {
        "risk": "Supply chain concentration",
        "severity": "High",
        "explanation": "Management said a large share of production depends on a few suppliers in one region.",
        "source": "Q&A, page 12",
    },
    {
        "risk": "Export restrictions",
        "severity": "High",
        "explanation": "New rules may limit sales of key products to some countries next quarter.",
        "source": "Risk factors, page 31",
    },
    {
        "risk": "Margin pressure",
        "severity": "Medium",
        "explanation": "Higher component costs may reduce gross margin in the coming quarters.",
        "source": "CFO remarks, page 6",
    },
    {
        "risk": "Foreign exchange",
        "severity": "Low",
        "explanation": "A stronger dollar had a small negative effect on revenue this quarter.",
        "source": None,
    },
]

COLORS = {
    "High": {"bg": "#e74c3c", "fg": "#ffffff"},
    "Medium": {"bg": "#f39c12", "fg": "#1a1a1a"},
    "Low": {"bg": "#2ecc71", "fg": "#1a1a1a"},
    "Unknown": {"bg": "#808080", "fg": "#ffffff"},
}

ORDER = {
    "High": 0,
    "Medium": 1,
    "Low": 2,
    "Unknown": 3,
}


def get_severity(risk):
    severity = risk.get("severity", "Unknown")

    if not isinstance(severity, str):
        return "Unknown"

    severity = severity.strip().capitalize()

    if severity not in ORDER:
        return "Unknown"

    return severity


def chip(severity):
    severity = severity if severity in COLORS else "Unknown"
    color = COLORS[severity]

    return (
        f"<span style='background:{color['bg']};"
        f"color:{color['fg']};padding:4px 10px;"
        f"border-radius:12px;font-size:0.8rem;"
        f"font-weight:600'>{severity}</span>"
    )


def render_risk_panel(risks):
    # Empty-state handling
    if not risks:
        st.info(
            "No risk data available yet. "
            "Upload and analyze a financial document to see risk highlights."
        )
        st.caption(
            "No detected risks does not necessarily mean "
            "the document is risk-free."
        )
        return

    # Normalize unexpected or missing severity values
    valid_risks = [
        r for r in risks
        if isinstance(r, dict)
    ]

    for risk in valid_risks:
        risk["severity"] = get_severity(risk)

    if not valid_risks:
        st.warning("Risk data could not be displayed. Please check the input.")
        return

    # Summary metrics
    counts = {
        severity: sum(
            1 for risk in valid_risks
            if risk["severity"] == severity
        )
        for severity in ORDER
    }

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("High", counts["High"])
    c2.metric("Medium", counts["Medium"])
    c3.metric("Low", counts["Low"])
    c4.metric("Unknown", counts["Unknown"])

    # Severity filter
    choice = st.multiselect(
        "Show severity",
        options=list(ORDER.keys()),
        default=list(ORDER.keys()),
    )

    # Sort risks by severity
    shown = sorted(
        [
            risk for risk in valid_risks
            if risk["severity"] in choice
        ],
        key=lambda risk: ORDER[risk["severity"]],
    )

    # Empty filter result
    if not shown:
        st.info(
            "No risks match your selected severity filters. "
            "Try selecting another severity."
        )
        return

    # Risk cards
    for risk in shown:
        with st.container(border=True):
            st.markdown(
                f"**{risk.get('risk', 'Unnamed risk')}** "
                f"&nbsp; {chip(risk['severity'])}",
                unsafe_allow_html=True,
            )

            st.write(
                risk.get("explanation")
                or "No explanation is available."
            )

            if risk.get("source"):
                st.caption(f"Source: {risk['source']}")


analysis = st.session_state.get("analysis")
if isinstance(analysis, dict) and isinstance(analysis.get("result"), dict):
    analysis = analysis["result"]

risk_data = analysis.get("risk") if isinstance(analysis, dict) else None
if isinstance(risk_data, dict):
    raw_risks = risk_data.get("risks", [])
elif isinstance(risk_data, list):
    raw_risks = risk_data
else:
    raw_risks = []

real_risks = []
for item in raw_risks:
    if not isinstance(item, dict):
        continue

    severity = item.get("severity", "Unknown")
    if isinstance(severity, (int, float)):
        severity = "High" if severity >= 4 else "Medium" if severity == 3 else "Low" if severity >= 1 else "Unknown"

    real_risks.append({
        "risk": item.get("title") or item.get("description") or item.get("category") or "Unspecified risk",
        "severity": severity,
        "explanation": item.get("explanation") or item.get("description") or "No explanation provided.",
        "source": item.get("quote") or item.get("source_quote"),
    })

if real_risks:
    render_risk_panel(real_risks)
else:
    st.info("Risk level: Unknown. The analysis did not verify any risks from the available evidence.")
    st.caption("Mock risks are no longer displayed.")
