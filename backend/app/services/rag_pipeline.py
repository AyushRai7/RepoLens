from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Chunking constants ─────────────────────────────────────────────────────────

CHUNK_SIZE    = 500   # approximate token count per chunk
CHUNK_OVERLAP = 80    # token overlap between adjacent chunks

_CHARS_PER_TOKEN = 4
_CHUNK_CHARS     = CHUNK_SIZE   * _CHARS_PER_TOKEN   # ~2000 chars
_OVERLAP_CHARS   = CHUNK_OVERLAP * _CHARS_PER_TOKEN  # ~320 chars


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_chars: int = _CHUNK_CHARS, overlap_chars: int = _OVERLAP_CHARS) -> List[str]:
    """
    Split text into overlapping character windows.

    Tries to break on newlines to avoid cutting mid-line.
    Returns a list of string chunks.

    Args:
        text:         The source text to chunk.
        chunk_chars:  Target size of each chunk in characters.
        overlap_chars: Number of characters to overlap between chunks.

    Returns:
        List of text chunks. Each chunk is at most chunk_chars characters.
    """
    if not text:
        return []

    chunks: List[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_chars, text_len)

        # Try to break on a newline near the end boundary
        if end < text_len:
            newline_pos = text.rfind("\n", start + chunk_chars // 2, end)
            if newline_pos != -1:
                end = newline_pos + 1  # include the newline

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Next chunk starts with overlap
        start = max(start + 1, end - overlap_chars)

    return chunks


def chunk_file(path: str, content: str, language: str, max_chars: int = _CHUNK_CHARS) -> List[dict]:
    """
    Chunk a single source file into overlapping segments with metadata.

    Args:
        path:      Repository-relative file path (used as metadata).
        content:   Raw source text.
        language:  Detected language string (e.g. "python", "typescript").
        max_chars: Maximum characters per chunk.

    Returns:
        List of dicts: {"text": str, "metadata": {"path": str, "language": str, "chunk_index": int}}
    """
    raw_chunks = chunk_text(content, chunk_chars=max_chars)
    return [
        {
            "text": chunk,
            "metadata": {
                "path": path,
                "language": language or "unknown",
                "chunk_index": i,
            },
        }
        for i, chunk in enumerate(raw_chunks)
    ]


# ── Index building ─────────────────────────────────────────────────────────────

def build_index(file_dicts: List[dict]):
    """
    Build a FAISS vector store from a list of source files.

    Args:
        file_dicts: List of {"path": str, "content": str, "language": str}.

    Returns:
        A FAISS VectorStore instance, or None if no content was found.

    Usage:
        vs = build_index(file_dicts)
        retriever = vs.as_retriever(search_kwargs={"k": 4})
    """
    try:
        from langchain_community.vectorstores import FAISS
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError:
            from langchain_community.embeddings import HuggingFaceEmbeddings  # noqa: deprecated

    except ImportError as e:
        logger.error("FAISS or HuggingFaceEmbeddings not installed: %s", e)
        return None

    texts: List[str] = []
    metadatas: List[dict] = []

    for file_info in file_dicts:
        path     = file_info.get("path", "")
        content  = file_info.get("content", "")
        language = file_info.get("language", "unknown")

        if not content or not path:
            continue

        for chunk in chunk_file(path, content, language):
            texts.append(chunk["text"])
            metadatas.append(chunk["metadata"])

    if not texts:
        logger.warning("build_index: no text content found — index will be empty")
        return None

    logger.info("Building FAISS index over %d chunks from %d files", len(texts), len(file_dicts))

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    vs = FAISS.from_texts(texts, embeddings, metadatas=metadatas)
    logger.info("FAISS index built: %d vectors", vs.index.ntotal)
    return vs


# ── Retriever helper ───────────────────────────────────────────────────────────

def get_retriever(file_dicts: List[dict], k: int = 4):
    """
    Build a FAISS index and return a LangChain retriever.

    Args:
        file_dicts: List of {"path": str, "content": str, "language": str}.
        k:          Number of chunks to return per query.

    Returns:
        A LangChain retriever, or None if the index could not be built.
    """
    vs = build_index(file_dicts)
    if vs is None:
        return None
    return vs.as_retriever(search_kwargs={"k": k})


# ── Similarity search (standalone, no LangChain) ──────────────────────────────

def search(query: str, file_dicts: List[dict], k: int = 4) -> List[dict]:
    """
    One-shot: build an index, run a query, return top-k results.

    Args:
        query:      The natural-language question.
        file_dicts: List of {"path", "content", "language"} dicts.
        k:          Number of results to return.

    Returns:
        List of {"text": str, "path": str, "language": str, "score": float}.

    This is mainly useful for testing or one-off queries.
    For production use, call get_retriever() once and reuse the retriever.
    """
    retriever = get_retriever(file_dicts, k=k)
    if retriever is None:
        return []

    docs = retriever.invoke(query)
    return [
        {
            "text": doc.page_content,
            "path": doc.metadata.get("path", "unknown"),
            "language": doc.metadata.get("language", "unknown"),
        }
        for doc in docs
    ]