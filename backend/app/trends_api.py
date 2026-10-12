"""GET /trends: cross-quarter trend insights (revenue QoQ, guidance beat/miss, tone, guidance-implied outlook).
Reads backend/app/trends.json, produced by scripts/export_trends.py (numbers only, no transcript quotes)."""
import json
from pathlib import Path

from fastapi import APIRouter

from app.api_contract import ApiError

router = APIRouter()
TRENDS_FILE = Path(__file__).with_name("trends.json")


@router.get(
    "/trends",
    tags=["records"],
    summary="Cross-quarter trends for the NVIDIA demo calls",
    description="Series with QoQ change, guidance-vs-actual tracking, hedging trend and a guidance-implied outlook. "
                "Computed by code from the extracted calls; the outlook is not a forecast.",
)
def get_trends():
    if not TRENDS_FILE.exists():
        raise ApiError(404, "trends_not_available",
                       "No trends data found. Run scripts/export_trends.py and rebuild.")
    return json.loads(TRENDS_FILE.read_text())
