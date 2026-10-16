# Autonomous Financial Analyst & Earnings Call Intelligence Agent

Built for the Nebius x NVIDIA Global AI Hackathon. Upload an earnings-call transcript or an SEC filing (PDF, TXT or HTML) and a team of AI agents will:

- **Extract** key metrics (revenue, margins, operating income, net income, EPS, guidance) with the exact source quote for each number.
- **Analyze** risk and management tone, with a severity rating for every risk and evidence for every claim.
- **Answer questions** about the document with citations.
- **Compare** quarters, show trends, and write a one-click analyst brief.

Everything runs on NVIDIA Nemotron models served by Nebius Token Factory. The main idea is that **the model proposes and code verifies**: every number and quote is checked against the source text before it reaches the user.

Live demo: https://financial-analyst-agent-v1.onrender.com (API docs at `/docs`)  <!-- keep only if the demo runs on permitted documents -->

## Architecture

```mermaid
flowchart LR
  UI[Streamlit dashboard] --> API[FastAPI backend]
  API --> ORCH[Orchestrator]
  ORCH --> EX[Extraction Agent]
  ORCH --> RS[Risk and Sentiment Agent]
  ORCH --> QA[Analyst Q&A Agent]
  EX --> LLM[(Nemotron on Nebius Token Factory)]
  RS --> LLM
  QA --> LLM
  EX --> VER[Verification layer]
  RS --> VER
  QA --> VER
  QA --> VS[(Vector store)]
  API --> DB[(Database)]
```

1. **Ingestion** (backend): files are uploaded, parsed (transcripts are split into prepared remarks and Q&A; SEC filings into sections and tables), stored, chunked and embedded.
2. **Orchestrator** (`agents/orchestrator.py`): routes a document through extraction, analysis and Q&A.
3. **Agents** (`agents/`): extraction (`extraction_agent.py`, `extract_filing.py`), risk and sentiment (`risk.py`, `risk_judge.py`, `sentiment.py`, `hedging.py`), Q&A with citations (`analyst.py`, `retrieval.py`), brief and trends (`brief.py`, `trends.py`).
4. **Verification layer** (`verify.py`, `verify_source.py`, `ground.py`): code checks on every model output (see "Reliability" below).
5. All model output is validated against Pydantic schemas (`agents/schemas.py`), with automatic retries on invalid JSON.


## How we use NVIDIA Nemotron and Nebius Token Factory
- All LLM calls go through Nebius Token Factory (OpenAI-compatible API). Default model: nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B, with reasoning turned off for fast, structured JSON.
- We benchmarked 5 models on the same 4 documents (23 values): see docs/benchmark_report.md.

| Model | Perfect runs (23/23) | Time per run | Approx. cost per run |
|---|---|---|---|
| Nemotron 3 Nano 30B (chosen) | 5 of 5 | 28 to 48 s | $0.005 to $0.007 |
| Nemotron 3 Super 120B | 4 of 4 | 29 to 34 s | about $0.023 |
| Nemotron 3.5 Lightning | 1 of 4 | 29 to 62 s | n/a |
| Qwen3-30B Instruct | 1 of 1 | 482 s | about $0.014 |
| gpt-oss-120b | 0 of 1 (19/23) | 41 s | about $0.018 |

Why Nano: same accuracy as the larger Nemotron model at roughly one third to one fifth of the cost per run.
Honest limits: small test, prompts tuned on Nemotron Nano, one to five runs per model.

## Reliability and evaluation
We do not trust the model alone. Checks run in code after every model call:
1. Every extracted number must appear in the source text next to its label, or it is dropped.
2. Impossible values are fixed or dropped (for example, a percent above 100).
3. Every quote used as evidence must exist in the document; a second pass rejects quotes that do not support the claim.
4. Unsupported claims are downgraded; if no risk can be verified, the rating is "unknown", never "low".
5. Hedging language is measured by counting phrases in code, not by asking the model.

| Test | Result |
|---|---|
| Extraction accuracy, 5 documents, 28 values | 28/28 correct, 0 hallucinated, 0 wrong, 0 missing |
| Quotes found verbatim in the source | 17 of 22 (weakest on PDFs) |
| Repeat runs on the same call (risk rating) | identical "high" in 6 of 6 runs; tone and hedging identical |
| Hosted smoke test (9 endpoints) | 9/9 passing |
| Q&A accuracy and citation rate (20 questions) | (TBD) |

Limits: the 5 documents are all from NVIDIA and were used while tuning the prompts, so scores are optimistic. Details: docs/verification_report.md, docs/stability_report.md.

## Run it

You need Python 3.11+ and a Nebius Token Factory API key.

```bash
git clone <this repo> && cd <repo folder>
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env        # then set NEBIUS_API_KEY
cd backend && uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs.

**With Docker (recommended):** the compose file builds from the project root so `agents/` is included. Run `cp .env.example .env`, set `NEBIUS_API_KEY`, then `docker compose up --build` and open http://127.0.0.1:8000/docs. The database and uploads are kept in a Docker volume, so they survive restarts.

Settings (environment variables): `NEBIUS_API_KEY` (required), `NEBIUS_MODEL` (optional, default `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`), `NEBIUS_THINKING` (`on` to enable the model's reasoning mode; default off).

Sample documents are not included for licensing reasons. Use any public earnings-call transcript or SEC 10-K/10-Q (public filings are available on sec.gov) in PDF, TXT or HTML.

## API

| Endpoint | What it does |
|---|---|
| `POST /upload` | Upload and index a document |
| `GET /documents`, `GET /documents/{id}` | List documents or read one |
| `POST /extract/{id}` | Extract metrics and guidance |
| `GET /documents/{id}/metrics` | Read stored metrics |
| `POST /analyze/{id}`, `GET /jobs/{job_id}` | Risk and sentiment analysis as a background job |
| `GET /documents/{id}/analysis` | Read the latest analysis |
| `POST /chat`, `GET /chat/{conversation_id}` | Ask questions with citations |
| `GET /companies`, `GET /metrics`, `GET /compare` | Query and compare records across quarters |
| `GET /trends` | Cross-quarter trends |
| `POST /brief/{id}` | One-click analyst brief |
| `GET /health` | Health check |

## Tests and evaluation

```bash
pytest                                  # backend tests
python scripts/contract_test.py         # agent contract tests
python3 -m scripts.eval_extraction      # extraction accuracy against hand-made answer keys
python3 -m scripts.benchmark_models     # model benchmark on Token Factory
python scripts/stability_check.py 2 3   # repeat-run stability on a hosted document
python scripts/hosted_smoke.py          # smoke test of the hosted endpoints
```

## Repo layout

- `agents/`   AI agents, prompts, verification, evaluation answer keys
- `backend/`  FastAPI service (ingestion, parsing, database, vector store, API)
- `frontend/` Streamlit dashboard
- `scripts/`  Tests, evaluation, benchmark, smoke test, demo seeding
- `docs/`     Architecture, API contract, evaluation and benchmark reports

## Team

Bhavana (lead, AI agents, evaluation), Sandeep (backend, ingestion, deployment), Alekhya (dashboard, sample data, demo).

## License

MIT, see [LICENSE](LICENSE).
