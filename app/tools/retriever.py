
from pathlib import Path
from functools import lru_cache

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path(__file__).resolve().parents[2]
POLICY_FILE = BASE_DIR / "data" / "returnPolicy.txt"


@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer("all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_chunks():
    if not POLICY_FILE.exists():
        raise FileNotFoundError(f"Policy file not found: {POLICY_FILE}")

    policy = POLICY_FILE.read_text(encoding="utf-8")
    chunks = [part.strip() for part in policy.split("\n\n") if part.strip()]

    if not chunks:
        raise ValueError("Policy file is empty.")

    return chunks


@lru_cache(maxsize=1)
def get_chunk_embeddings():
    return get_model().encode(get_chunks())


def retrieve_policy(query: str, top_k: int = 2):
    if not query.strip():
        return []

    chunks = get_chunks()
    embeddings = get_chunk_embeddings()
    query_embedding = get_model().encode([query])

    scores = cosine_similarity(query_embedding, embeddings)[0]
    indices = scores.argsort()[::-1][:max(1, top_k)]

    return [
        {"text": chunks[i], "score": float(scores[i])}
        for i in indices
    ]
