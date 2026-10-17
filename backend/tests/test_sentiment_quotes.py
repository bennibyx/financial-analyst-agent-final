import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents import sentiment


def run_filter(monkeypatch, transcript, data):
    captured = {}

    def fake_ask_json(system, prompt, schema, **kwargs):
        captured["result"] = kwargs["pre"](data.copy())
        return captured["result"], 0

    monkeypatch.setattr(sentiment, "ask_json", fake_ask_json)
    sentiment._analyze_sentiment_model(transcript)
    return captured["result"]


def base_data(quotes):
    return {
        "overall": "positive",
        "score": 0.6,
        "hedging_level": "low",
        "qa_pushback": "none",
        "evidence_quotes": quotes,
    }


def test_genuine_quote_is_preserved(monkeypatch):
    quote = "Revenue increased because customer demand remained strong."
    result = run_filter(
        monkeypatch, quote, base_data(["TONE: " + quote])
    )
    assert result["evidence_quotes"] == ["TONE: " + quote]


def test_fabricated_quote_is_removed(monkeypatch):
    transcript = "Revenue increased because customer demand remained strong."
    result = run_filter(
        monkeypatch,
        transcript,
        base_data(["TONE: Revenue doubled in every region this year."]),
    )
    assert result["evidence_quotes"] == []


def test_mixed_quote_keeps_verifiable_sentence(monkeypatch):
    genuine = "Revenue increased because customer demand remained strong."
    transcript = genuine + " Costs also fell sharply across all regions."
    result = run_filter(
        monkeypatch,
        transcript,
        base_data([
            "TONE: " + genuine + " This proves profits will double next quarter."
        ]),
    )
    assert result["evidence_quotes"] == ["TONE: " + genuine]


def test_unsupported_quotes_downgrade_sentiment_claims(monkeypatch):
    result = run_filter(
        monkeypatch,
        "We delivered record revenue this quarter.",
        {
            "overall": "positive",
            "score": 0.7,
            "hedging_level": "high",
            "qa_pushback": "strong",
            "evidence_quotes": [
                "PUSHBACK: Why are you concerned about the falling margins?",
                "HEDGING: Results may be materially lower than expected.",
            ],
        },
    )
    assert result["evidence_quotes"] == []
    assert result["qa_pushback"] == "none"
    assert result["hedging_level"] == "low"
