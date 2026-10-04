flowchart LR
  UI[Streamlit UI] --> API[FastAPI backend]
  API --> ORCH[Orchestrator]
  ORCH --> EX[Extraction Agent]
  ORCH --> RS[Risk & Sentiment Agent]
  ORCH --> QA[Analyst Q&A Agent]
  EX --> LLM[(Nemotron on Nebius)]
  RS --> LLM
  QA --> LLM
  QA --> VS[(Vector store)]
  API --> DB[(Database)]