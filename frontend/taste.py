# taste.py -- tiny preview of our real UI, with FAKE data
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Fin Analyst Agent", layout="wide")
st.title("📊 Financial Analyst Agent")

# Sidebar = navigation panel on the left
page = st.sidebar.radio("Go to", ["Upload", "Analysis", "Chat"])

if page == "Upload":
    # File uploader widget: returns the file once the user drops one in
    file = st.file_uploader("Upload transcript or filing", type=["pdf", "txt", "html"])
    company = st.text_input("Company")
    if st.button("Analyze"):
        if file is None:
            st.error("Please upload a file first.")   # red error box
        else:
            st.success(f"Received {file.name} for {company}")

elif page == "Analysis":
    tab1, tab2 = st.tabs(["Metrics", "Sentiment"])
    with tab1:
        # Fake metrics -- later this comes from the backend API as JSON
        df = pd.DataFrame({
            "Metric": ["Revenue ($B)", "EPS ($)", "Gross Margin (%)"],
            "Value": [4.2, 1.12, 61.5],
            "QoQ %": [3.1, -2.0, 0.4],
            "YoY %": [12.4, 8.0, 1.2],
        })
        st.dataframe(df, use_container_width=True)
    with tab2:
        s = pd.DataFrame({"Section": ["Prepared", "Q&A"], "Sentiment": [0.45, 0.18]})
        st.plotly_chart(px.bar(s, x="Section", y="Sentiment"), use_container_width=True)

else:
    # Chat UI: st.chat_message and st.chat_input are built in
    with st.chat_message("assistant"):
        st.write("Ask me anything about the report.")
    q = st.chat_input("Your question")
    if q:
        with st.chat_message("user"):
            st.write(q)
