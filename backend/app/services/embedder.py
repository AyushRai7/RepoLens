from __future__ import annotations

import logging
from functools import lru_cache
from typing import List

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Model name ─────────────────────────────────────────────────────────────────

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384  # output dimension of this model


# ── Singleton loader ───────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """
    Load the model once and cache it for the lifetime of the process.
    lru_cache(maxsize=1) means it's only ever loaded once, even if
    embed_texts() is called thousands of times.
    """
    logger.info("Loading embedding model: %s", MODEL_NAME)
    model = SentenceTransformer(MODEL_NAME)
    logger.info("Embedding model loaded. Dimension: %d", EMBEDDING_DIM)
    return model


# ── Public API ─────────────────────────────────────────────────────────────────

def embed_texts(texts: List[str], batch_size: int = 64) -> List[List[float]]:
    """
    Embed a list of text strings into 384-dim float vectors.

    Args:
        texts:      List of strings to embed. Can be code chunks,
                    docstrings, function signatures, or questions.
        batch_size: How many texts to encode in one forward pass.
                    Larger = faster but uses more RAM. 64 is safe
                    for most machines.

    Returns:
        List of embeddings, one per input text. Each embedding is
        a plain Python list of 384 floats (not numpy) so it can be
        JSON-serialised and stored in pgvector.

    Example:
        >>> vecs = embed_texts(["def foo(): pass", "import os"])
        >>> len(vecs[0])
        384
    """
    if not texts:
        return []

    model = _get_model()

    logger.debug("Embedding %d texts in batches of %d", len(texts), batch_size)

    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,   
    )

    return embeddings.tolist()


def embed_single(text: str) -> List[float]:
    """
    Convenience wrapper to embed a single string.
    Used at query time to embed the user's chat question.

    Args:
        text: The string to embed (e.g. a user's question).

    Returns:
        A single 384-dim float list.
    """
    results = embed_texts([text])
    return results[0]


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    Returns a float in [-1, 1]. Higher = more similar.

    Note: pgvector handles similarity search in SQL, so this function
    is mainly useful for local testing / unit tests.
    """
    a = np.array(vec_a)
    b = np.array(vec_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)