"""Text to vectors. Local only: no text leaves the machine for embedding."""

import hashlib
import math
import re
import threading
from pathlib import Path
from typing import Protocol

DIMENSIONS = (
    384  # the size of the `chunks.embedding` column; a model with another size needs a migration
)


class Embedder(Protocol):
    name: str

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    """BAAI/bge-small-en-v1.5 (384 dimensions) through FastEmbed's ONNX runtime, on the CPU.

    The model (about 130 MB) downloads on first use into `cache_dir`.
    """

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.name = model_name
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding  # imported late: it is slow to import

                self._model = TextEmbedding(self.name, cache_dir=str(self._cache_dir))
            return self._model

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        with self._lock:  # one inference at a time keeps memory predictable
            return [vector.tolist() for vector in model.embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        model = self._load()
        with self._lock:
            return next(iter(model.query_embed(text))).tolist()


class HashEmbedder:
    """Deterministic stand-in for tests: words are hashed into a bag-of-words vector.

    Texts that share words get similar vectors, which is enough to exercise the pipeline
    without downloading a model. It is not a quality embedder.
    """

    name = "hash-384"

    def _vector(self, text: str) -> list[float]:
        vector = [0.0] * DIMENSIONS
        for word in re.findall(r"[a-z0-9]{2,}", text.lower()):
            digest = hashlib.blake2b(word.encode(), digest_size=4).digest()
            bucket = int.from_bytes(digest, "big") % DIMENSIONS
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def make_embedder(kind: str, model_name: str, cache_dir: Path) -> Embedder:
    return HashEmbedder() if kind == "hash" else FastEmbedder(model_name, cache_dir)
