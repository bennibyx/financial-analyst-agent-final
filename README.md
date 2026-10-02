# Autonomous Financial Analyst & Earnings Call Intelligence Agent

Nebius x NVIDIA Global AI Hackathon project. Upload earnings-call transcripts or
SEC filings; agents extract metrics, analyze risk and sentiment, and answer
questions with citations.

> README is a stub (Day 1). Full setup, architecture and Nemotron / Nebius
> Token Factory usage will be added by Day 22.

## Quick start (backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env                            # then fill in values
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/health and http://127.0.0.1:8000/docs

## Folders

- `backend/`  FastAPI service (Sandeep)
- `agents/`   AI agents and prompts (Bhavana)
- `schemas/`  Shared JSON schemas
- `frontend/` Dashboard (Alekhya)
- `docs/`     Architecture and API docs
- `data/samples/` Sample documents (not committed)

## License

MIT, see [LICENSE](LICENSE).
