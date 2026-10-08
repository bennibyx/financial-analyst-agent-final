from math import sqrt
from collections import Counter


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def embed_text(text: str) -> dict[str, float]:
    tokens = _tokenize(text)

    if not tokens:
        return {}

    counts = Counter(tokens)
    total = sum(counts.values())

    return {
        token: count / total
        for token, count in counts.items()
    }


def cosine_similarity(
    vector_a: dict[str, float],
    vector_b: dict[str, float],
) -> float:
    if not vector_a or not vector_b:
        return 0.0

    common = set(vector_a) & set(vector_b)

    dot_product = sum(
        vector_a[token] * vector_b[token]
        for token in common
    )

    magnitude_a = sqrt(sum(value * value for value in vector_a.values()))
    magnitude_b = sqrt(sum(value * value for value in vector_b.values()))

    if magnitude_a == 0 or magnitude_b == 0:
        return 0.0

    return dot_product / (magnitude_a * magnitude_b)


def search_chunks(
    query: str,
    chunks: list[dict],
    top_k: int = 3,
) -> list[dict]:
    query_vector = embed_text(query)

    scored = []

    for chunk in chunks:
        vector = embed_text(chunk["text"])
        score = cosine_similarity(query_vector, vector)

        scored.append({
            **chunk,
            "score": score,
        })

    scored.sort(key=lambda item: item["score"], reverse=True)

    return scored[:top_k]
def search_database_chunks(db, query: str, top_k: int = 3) -> list[dict]:
    from ..models import Chunk

    chunks = db.query(Chunk).all()

    chunk_data = [
        {
            "id": chunk.id,
            "document_id": chunk.document_id,
            "text": chunk.text,
        }
        for chunk in chunks
    ]

    return search_chunks(query, chunk_data, top_k)