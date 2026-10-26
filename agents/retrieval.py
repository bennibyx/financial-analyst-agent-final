# agents/retrieval.py -- embed chunks and find the most relevant ones (cosine similarity, numpy only)
import os, json, pathlib
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI
from .chunking import chunk_document
from .verify import clean_text

load_dotenv()
_client = None  # created on first use, so importing this module never needs API keys


def get_client():
    """Build the Token Factory client lazily (keys are only needed when a call is made)."""
    global _client
    if _client is None:
        _client = OpenAI(base_url="https://api.tokenfactory.nebius.com/v1/",
                         api_key=os.environ["NEBIUS_API_KEY"])
    return _client


def embed_model():
    return os.environ["NEBIUS_EMBED_MODEL"]

BATCH = 16  # texts per API call; keeps each request small

def embed(texts):
    """Turn a list of texts into a (n, 4096) numpy array, unit-length so dot product = cosine."""
    vecs = []
    for i in range(0, len(texts), BATCH):
        resp = get_client().embeddings.create(model=embed_model(), input=texts[i:i + BATCH])
        vecs.extend(d.embedding for d in resp.data)
    arr = np.array(vecs, dtype=np.float32)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)

def build_index(text, doc_id, cache_dir="data/index"):
    """Chunk + embed a document once; reuse the saved files on later runs."""
    d = pathlib.Path(cache_dir); d.mkdir(parents=True, exist_ok=True)
    import hashlib  # cache key = id + content hash, so changed text can never reuse a stale index
    key = f"{doc_id}-{hashlib.sha1(text.encode('utf-8', 'replace')).hexdigest()[:10]}"
    vec_file, meta_file = d / f"{key}.npy", d / f"{key}.json"
    if vec_file.exists() and meta_file.exists():
        return np.load(vec_file), json.loads(meta_file.read_text())
    chunks = chunk_document(clean_text(text), doc_id)
    print(f"embedding {len(chunks)} chunks...", flush=True)
    vectors = embed([c.text for c in chunks])
    meta = [{"chunk_id": c.chunk_id, "section": c.section, "text": c.text} for c in chunks]
    np.save(vec_file, vectors)
    meta_file.write_text(json.dumps(meta))
    return vectors, meta

def search(query, vectors, meta, k=3):
    """Return the top-k chunks for a question, with similarity scores."""
    q = embed([query])[0]
    scores = vectors @ q                       # cosine similarity (vectors are unit length)
    top = np.argsort(-scores)[:k]
    return [{**meta[i], "score": float(scores[i])} for i in top]
