import pytest


from app.vectorstore.store import (
    cosine_similarity,
    embed_text,
    search_chunks,
)


def test_embed_text():
    vector = embed_text("revenue growth revenue")

    assert vector["revenue"] == 2 / 3
    assert vector["growth"] == 1 / 3


def test_cosine_similarity():
    vector_a = embed_text("revenue growth")
    vector_b = embed_text("revenue growth")

    assert cosine_similarity(vector_a, vector_b) == pytest.approx(1.0)


def test_search_chunks_ranks_relevant_chunk_first():
    chunks = [
        {"id": 1, "text": "revenue increased significantly"},
        {"id": 2, "text": "gross margin remained stable"},
        {"id": 3, "text": "competition is a risk"},
    ]

    results = search_chunks("revenue growth", chunks, top_k=2)

    assert len(results) == 2
    assert results[0]["id"] == 1
    assert results[0]["score"] > results[1]["score"]