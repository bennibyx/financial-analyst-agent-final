
import streamlit as st
import api_client

st.set_page_config(
    page_title="Fin Analyst Agent",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Financial Analyst Agent")
st.caption("Upload an earnings call or SEC filing to analyze it.")

file = st.file_uploader(
    "Transcript or filing",
    type=["pdf", "txt", "html"],
)

c1, c2, c3 = st.columns(3)

company = c1.text_input("Company", placeholder="e.g. NVIDIA")
quarter = c2.selectbox(
    "Quarter",
    ["Q4 FY26", "Q1 FY27", "Q2 FY27"],
)
doc_type = c3.selectbox(
    "Document type",
    ["Earnings call", "CFO commentary", "10-Q", "10-K"],
)

if st.button("Analyze", type="primary"):
    if file is None:
        st.error("Please upload a file first.")
    elif not company.strip():
        st.error("Please enter the company name.")
    else:
        try:
            with st.spinner("Uploading document to backend..."):
                upload_result = api_client.upload_document(file)

            st.success("Document uploaded successfully!")

            with st.expander("Backend upload response"):
                st.json(upload_result)

            # Keep mock analysis until the real analysis API is integrated.
            st.session_state["analysis"] = api_client.get_analysis(
                company=company,
                quarter=quarter,
            )

            st.info(
                f"Document type: {doc_type}. "
                "Analysis is still using mock data."
            )
            st.success(
                "Mock analysis ready. Open Analysis in the sidebar."
            )

        except (RuntimeError, OSError, ValueError) as exc:
            st.error(f"Upload or analysis failed: {exc}")
