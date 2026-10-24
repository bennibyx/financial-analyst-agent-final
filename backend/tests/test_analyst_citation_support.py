
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agents import analyst


def run_with_model(question, text, answer, support_ids):
    fake_output = analyst.ModelOut(
        answerable=True,
        answer=answer,
        support_ids=support_ids,
    )

    with (
        patch.object(analyst, "build_index", return_value=("vectors", "meta")),
        patch.object(
            analyst,
            "search",
            return_value=[
                {
                    "text": text,
                    "chunk_id": "chunk-1",
                    "score": 1.0,
                }
            ],
        ),
        patch.object(
            analyst,
            "ask_json",
            return_value=(fake_output, 0),
        ),
    ):
        return analyst.answer_question(
            question,
            text,
            doc_id="test-doc",
        )


def test_relevant_verbatim_citation_is_kept():
    text = (
        "Revenue declined by 12 percent due to supply constraints.\n"
        "The company opened a new office in London."
    )

    result = run_with_model(
        "Why did revenue decline?",
        text,
        "Revenue declined because of supply constraints.",
        ["S1"],
    )

    assert result["result"]["answer"] != analyst.NOT_FOUND
    assert any(
        "supply constraints" in citation["quote"]
        for citation in result["result"]["citations"]
    )


def test_irrelevant_verbatim_citation_is_not_treated_as_support():
    text = (
        "Revenue declined by 12 percent due to supply constraints.\n"
        "The company opened a new office in London."
    )

    result = run_with_model(
        "Why did revenue decline?",
        text,
        "Revenue declined because of supply constraints.",
        ["S2"],
    )

    assert result["result"]["answer"] == analyst.NOT_FOUND
    assert result["result"]["citations"] == []


def test_answer_number_must_be_present_in_citations():
    text = (
        "Revenue declined by 12 percent due to supply constraints.\n"
        "The company opened a new office in London."
    )

    result = run_with_model(
        "What was the revenue decline?",
        text,
        "Revenue declined by 99 percent.",
        ["S1"],
    )

    assert result["result"]["answer"] == analyst.NOT_FOUND
    assert result["result"]["citations"] == []


def test_contradictory_answer_is_rejected():
    text = "Revenue increased by 18 percent."

    result = run_with_model(
        "How did revenue change?",
        text,
        "Revenue decreased by 18 percent.",
        ["S1"],
    )

    assert result["result"]["answer"] == analyst.NOT_FOUND
    assert result["result"]["citations"] == []


def test_valid_direction_for_one_metric_is_not_rejected():
    text = (
        "Revenue increased by 10 percent, while "
        "operating costs decreased by 5 percent."
    )

    result = run_with_model(
        "How did operating costs change?",
        text,
        "Operating costs decreased by 5 percent.",
        ["S1"],
    )

    assert result["result"]["answer"] != analyst.NOT_FOUND
