import time
import streamlit as st
import api_client

st.set_page_config(page_title="Fin Analyst Agent", page_icon="📊", layout="wide")
st.title("📊 Financial Analyst Agent")
st.caption("Upload an earnings call or SEC filing to analyze it.")

file = st.file_uploader("Transcript or filing", type=["pdf", "txt", "html"])
c1, c2, c3 = st.columns(3)
company = c1.text_input("Company", placeholder="e.g. NVIDIA")
quarter = c2.selectbox("Quarter", ["Q4 FY26", "Q1 FY27", "Q2 FY27"])
doc_type = c3.selectbox("Document type", ["Earnings call", "CFO commentary", "10-Q", "10-K"])

if st.button("Analyze", type="primary"):
    if file is None:
        st.error("Please upload a file first.")
    elif not company.strip():
        st.error("Please enter the company name.")
    else:
        with st.status("Analyzing...", expanded=True) as status:
            for step in ["Parsing document", "Extracting metrics", "Analyzing risk and sentiment"]:
                st.write(f"⏳ {step}...")
                time.sleep(1)  # fake delay; real progress comes on Day 10
            # session_state remembers data while you move between pages
            st.session_state["analysis"] = api_client.get_analysis(company, quarter)
            status.update(label="Done", state="complete")
        st.success("Analysis ready. Open **Analysis** in the sidebar.")