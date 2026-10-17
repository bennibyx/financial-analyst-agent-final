
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
    "but the current analysis endpoint does not support them yet."
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
        progress = st.progress(0)
        status_message = st.empty()

        try:
            # Step 1: Upload, parse, and prepare the document.
            status_message.info(
                "Step 1 of 3: Uploading and preparing the document..."
            )
            progress.progress(5)

            upload_result = api_client.ingest_document(uploaded_file)

            document_id = upload_result.get("document_id")
            doc_type = str(upload_result.get("doc_type", "")).lower()

            if document_id is None:
                status_message.error(
                    "The backend did not return a document ID."
                )
                st.stop()

            st.session_state["document_id"] = document_id
            st.session_state["upload_result"] = upload_result

            progress.progress(35)
            status_message.success(
                "Step 1 of 3 complete: Document uploaded and prepared."
            )

            st.success(
                f"Document uploaded successfully. Document ID: {document_id}"
            )
            st.write(f"**Detected document type:** {doc_type or 'unknown'}")

            if doc_type not in {"transcript", "commentary"}:
                progress.progress(100)
                status_message.warning(
                    "Upload completed, but real analysis was not started. "
                    "The current endpoint supports transcripts and commentary "
                    "only. If this is an earnings-call transcript, check the "
                    "filename and detected document type."
                )
                st.stop()

            # Step 2: Start the real analysis job.
            status_message.info(
                "Step 2 of 3: Starting risk and sentiment analysis..."
            )

            job_result = api_client.start_analysis(document_id)

            job_id = job_result.get("job_id")
            status = str(job_result.get("status", "")).lower()

            if job_id is None:
                status_message.error(
                    f"The backend did not return a job ID: {job_result}"
                )
                st.stop()

            st.session_state["job_id"] = job_id
            st.write(f"**Analysis job ID:** {job_id}")

            progress.progress(45)

            # Step 3: Poll until analysis finishes.
            status_message.info(
                "Step 3 of 3: Analyzing risks and sentiment..."
            )

            started_at = time.time()
            timeout_seconds = 300

            while status in {"queued", "running"}:
                elapsed = time.time() - started_at

                if elapsed >= timeout_seconds:
                    status_message.warning(
                        "Analysis is taking longer than expected. "
                        "You can revisit this page and try checking the "
                        "document again."
                    )
                    break

                # Progress reflects elapsed time, not internal backend stages.
                estimated_progress = min(
                    45 + int((elapsed / timeout_seconds) * 50),
                    95,
                )
                progress.progress(estimated_progress)

                status_message.info(
                    f"Step 3 of 3: Analysis {status} "
                    f"({int(elapsed)} seconds elapsed)..."
                )

                time.sleep(2)
                job_result = api_client.get_job(job_id)
                status = str(job_result.get("status", "")).lower()

            if status == "done":
                analysis = job_result.get("result")

                if analysis is None:
                    analysis = job_result.get("analysis")

                if analysis is None:
                    analysis = job_result.get("data")

                if analysis is None:
                    status_message.error(
                        "The job completed, but no analysis result was "
                        "returned by the backend."
                    )
                    st.json(job_result)
                else:
                    st.session_state["analysis"] = analysis
                    st.session_state["analysis_document_id"] = document_id

                    progress.progress(100)
                    status_message.success(
                        "All 3 steps complete! Risk and sentiment analysis "
                        "finished successfully."
                    )

                    st.rerun()

            elif status == "failed":
                error_detail = job_result.get("error", job_result)
                status_message.error(
                    f"Analysis failed: {error_detail}"
                )

            elif status in {"queued", "running"}:
                # Timed out while the job may still be processing.
                st.info(
                    f"Job {job_id} is still {status}. "
                    "Revisit this page to retry the upload workflow, "
                    "or check the job status through the backend."
                )

            else:
                status_message.warning(
                    f"Unexpected job status: {status or 'unknown'}"
                )
                st.json(job_result)

        except Exception as exc:
            status_message.error(f"Upload or analysis failed: {exc}")

analysis = st.session_state.get("analysis")

if analysis:
    st.divider()
    st.header("Analysis Results")

    sentiment = analysis.get("sentiment", {})
    risk = analysis.get("risk", {})
    issues = analysis.get("issues", [])
    errors = analysis.get("errors", [])

    st.subheader("Sentiment")

    if isinstance(sentiment, dict) and sentiment:
        st.json(sentiment)
    elif sentiment:
        st.write(sentiment)
    else:
        st.info("No sentiment details were returned.")

    st.subheader("Risk Assessment")

    if isinstance(risk, dict):
        overall_risk = risk.get("overall_risk_level")

        if overall_risk is not None:
            st.metric("Overall Risk Level", str(overall_risk).upper())

        risks = risk.get("risks", [])

        if risks:
            for index, item in enumerate(risks, start=1):
                title = (
                    item.get("title", f"Risk {index}")
                    if isinstance(item, dict)
                    else f"Risk {index}"
                )

                with st.expander(title):
                    if isinstance(item, dict):
                        st.json(item)
                    else:
                        st.write(item)
        else:
            st.write("No individual risks were returned.")
    elif risk:
        st.write(risk)
    else:
        st.info("No risk details were returned.")

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
        f"Last uploaded document ID: "
        f"{st.session_state['document_id']}"
    )
