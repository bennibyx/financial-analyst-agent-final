"""All backend calls live here. Today: mock data. Days 9-14: real API calls."""
import json
from pathlib import Path

USE_MOCK = True
_MOCK_FILE = Path(__file__).parent / "mock_analysis.json"


def get_analysis(company=None, quarter=None):
    """Return the analysis JSON (metrics, risks, sentiment, guidance, citations)."""
    if USE_MOCK:
        return json.loads(_MOCK_FILE.read_text())
    raise NotImplementedError("Real API call comes on Days 9-12")


def ask_question(question, history):
    """Return {'answer': str, 'citations': [...]}."""
    if USE_MOCK:
        data = get_analysis()
        return {
            "answer": "Mock answer: gross margin rose because of a better product mix [1][2].",
            "citations": data["citations"],
        }
    raise NotImplementedError("Real API call comes on Day 14")