"""Document upload page for the Financial Analyst Agent."""

import time

import streamlit as st

import api_client


st.set_page_config(
    page_title="Financial Analyst Agent — Upload",
    page_icon="📊",
    layout="wide",
)

st.title("📄 Upload Financial Document")
st.write(
    "Upload an earnings-call transcript or CFO commentary "
    "to run real risk and sentiment analysis."
)

st.info(
    "Real analysis currently supports earnings-call transcripts "
    "and CFO commentary. 10-K and 10-Q filings can be uploaded, "
    "but this analysis endpoint does not support them yet."
)

uploaded_file = st.file_uploader(
    "Choose a document",
    type=["pdf", "txt", "html", "htm"],
    help="Supported formats: PDF, TXT, HTML.",
)

if uploaded_file is not None:
    st.write(f"**File:** {uploaded_file.name}")
    st.write(f"**Size:** {uploaded_file.size:,} bytes")

    if st.button("Upload and Analyze", type="primary"):
        try:
            with st.spinner("Uploading and processing document..."):
                upload_result = api_client.ingest_document(uploaded_file)

            document_id = upload_result.get("document_id")
            doc_type = str(upload_result.get("doc_type", "")).lower()

            if document_id is None:
                st.error("The backend did not return a document ID.")
                st.stop()

            st.session_state["document_id"] = document_id
            st.session_state["upload_result"] = upload_result

            st.success(
                f"Document uploaded successfully. Document ID: {document_id}"
            )

            st.write(f"**Detected document type:** {doc_type or 'unknown'}")

            if doc_type not in {"transcript", "commentary"}:
                st.warning(
                    "The document was saved, but the current real-analysis "
                    "endpoint supports only transcripts and commentary. "
                    "No analysis job was started. If this is an earnings-call "
                    "transcript, check the filename and try again."
                )
                st.stop()

            with st.spinner("Starting real risk and sentiment analysis..."):
                job_result = api_client.start_analysis(document_id)

            job_id = job_result.get("job_id")
            status = str(job_result.get("status", "")).lower()

            if job_id is None:
                st.error(f"The backend did not return a job ID: {job_result}")
                st.stop()

            st.session_state["job_id"] = job_id
            st.write(f"**Analysis job ID:** {job_id}")

            progress = st.progress(0)
            status_message = st.empty()
            started_at = time.time()
            timeout_seconds = 300

            while status in {"queued", "running"}:
                elapsed = time.time() - started_at

                if elapsed >= timeout_seconds:
                    status_message.warning(
                        "Analysis is taking longer than expected. "
                        "You can refresh or revisit this page to check again."
                    )
                    break

                status_message.info(
                    f"Analysis status: {status} "
                    f"({int(elapsed)} seconds elapsed)"
                )
                progress.progress(min(int(elapsed / timeout_seconds * 100), 95))

                time.sleep(2)
                job_result = api_client.get_job(job_id)
                status = str(job_result.get("status", "")).lower()

            if status == "done":
                analysis = job_result.get("result")

                if analysis is None:
                    analysis = job_result.get("analysis")

                if analysis is None:
                    # Some API responses may expose the stored JSON under data.
                    analysis = job_result.get("data")

                if analysis is None:
                    st.error(
                        "The job completed, but no analysis result was "
                        f"returned. Response: {job_result}"
                    )
                else:
                    st.session_state["analysis"] = analysis
                    st.session_state["analysis_document_id"] = document_id
                    progress.progress(100)
                    status_message.success("Real analysis completed.")
                    st.rerun()

            elif status == "failed":
                st.error(f"Analysis failed: {job_result.get('error', job_result)}")

            elif status not in {"queued", "running"}:
                st.warning(f"Unexpected job status: {status or 'unknown'}")
                st.json(job_result)

        except Exception as exc:
            st.error(f"Upload or analysis failed: {exc}")


analysis = st.session_state.get("analysis")

if analysis:
    st.divider()
    st.header("Analysis Results")

    sentiment = analysis.get("sentiment", {})
    risk = analysis.get("risk", {})
    issues = analysis.get("issues", [])
    errors = analysis.get("errors", [])

    st.subheader("Sentiment")
    if isinstance(sentiment, dict):
        st.json(sentiment)
    else:
        st.write(sentiment if sentiment else "No sentiment details returned.")

    st.subheader("Risk Assessment")
    if isinstance(risk, dict):
        overall_risk = risk.get("overall_risk_level")
        if overall_risk is not None:
            st.metric("Overall Risk Level", str(overall_risk))

        risks = risk.get("risks", [])
        if risks:
            for index, item in enumerate(risks, start=1):
                with st.expander(f"Risk {index}"):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        else:
            st.write("No individual risks were returned.")
    else:
        st.write(risk if risk else "No risk details returned.")

    if issues:
        st.subheader("Issues")
        st.json(issues)

    if errors:
        st.subheader("Analysis Warnings / Errors")
        st.json(errors)

    with st.expander("Raw analysis response"):
        st.json(analysis)

elif st.session_state.get("document_id") is not None:
    st.caption(
        f"Last uploaded document ID: {st.session_state['document_id']}"
    )
