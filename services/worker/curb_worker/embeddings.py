"""Local embeddings via fastembed (ONNX, no torch).

Single global encoder so the model loads once. BAAI/bge-small-en-v1.5
gives 384-dim vectors which matches pgvector(384) in the schema.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from fastembed import TextEmbedding

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384


@lru_cache(maxsize=1)
def _encoder() -> TextEmbedding:
    """Build (and cache) the encoder. First call triggers ONNX model download."""
    return TextEmbedding(model_name=MODEL_NAME)


def embed_one(text: str) -> list[float]:
    """Embed a single string. Returns a 384-dim Python list of floats."""
    vec = next(iter(_encoder().embed([text])))
    out: list[float] = vec.tolist()
    return out


def embed_many(texts: Iterable[str]) -> list[list[float]]:
    """Embed an iterable of strings; preserves order."""
    return [v.tolist() for v in _encoder().embed(list(texts))]
