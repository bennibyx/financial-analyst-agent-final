from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Autonomous Financial Analyst & Earnings Call Intelligence API",
    version="0.1.0",
    description="Backend: document upload, parsing, storage and agent endpoints.",
)


@app.get("/health", tags=["system"])
def health():
    """Liveness check used by Docker, the hosting platform and the team."""
    return {
        "status": "ok",
        "service": "financial-analyst-api",
        "version": app.version,
        "nebius_key_configured": bool(settings.nebius_api_key),
    }
