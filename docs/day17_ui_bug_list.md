# Day 17 — UI Bug List

## Test environment
- Application: Financial Analyst Agent
- Framework: Streamlit
- Test date: 20 October 2026

## Test 1 — Upload a document
- Result: A document was accepted and the UI displayed a processed status.
- Observation: The response displayed demo data (`doc_id: demo-001`, company: Apple).
- Follow-up: Verify whether the upload is connected to the real ingestion API.

## Test 2 — Financial metrics and CSV export
- Result: The metrics page displayed six metrics and the CSV downloaded successfully.
- Follow-up: Compare exported values with the expected results and confirm the required CSV format.

## Test 3 — Pending
- Document: To be selected
- Result: Pending

## Other pages
- Risks: Pending
- Sentiment: Pending
- Chat: Pending

## Bugs and follow-up items
1. Verify whether document processing uses the real backend or mock data.
2. Verify CSV values and formatting against expected results.
3. Record any additional reproducible UI issues discovered during testing.