"""Embedding generation via Ollama, with an offline fallback backend."""

import hashlib
import json
import math
import os
import re
from typing import Dict, List

import requests

from config import (
    CORPUS_INDEX_PATH,
    EMBEDDINGS_CACHE_PATH,
    EMBEDDING_MODEL,
    OLLAMA_BASE_URL,
)

HASH_DIMS = 512


class EmbeddingManager:
    """
    Manages embeddings with two backends.

    backend="ollama"  real local embeddings, required for thesis results
    backend="hash"    dependency-free deterministic vectors, for pipeline testing only
    backend="auto"    use ollama if reachable, otherwise fall back to hash
    """

    def __init__(
        self,
        model: str = EMBEDDING_MODEL,
        base_url: str = OLLAMA_BASE_URL,
        backend: str = "auto",
    ):
        self.model = model
        self.base_url = base_url
        self.backend = self._resolve_backend(backend)
        self.cache = self._load_json(EMBEDDINGS_CACHE_PATH)
        self.corpus_index = self._load_json(CORPUS_INDEX_PATH)
        self._pending_writes = 0

    def _resolve_backend(self, requested: str) -> str:
        if requested == "hash":
            return "hash"
        reachable = self._ollama_reachable()
        if requested == "ollama":
            if not reachable:
                raise RuntimeError(
                    f"Ollama not reachable at {self.base_url}. "
                    "Start it with `ollama serve` and `ollama pull nomic-embed-text`, "
                    "or use backend='hash' for pipeline testing."
                )
            return "ollama"
        if reachable:
            return "ollama"
        print(
            "\n" + "!" * 68 +
            "\n! Ollama unavailable - falling back to HASH embeddings."
            "\n! Pipeline testing only. Results are NOT valid for the thesis."
            "\n" + "!" * 68 + "\n"
        )
        return "hash"

    def _ollama_reachable(self) -> bool:
        try:
            return requests.get(f"{self.base_url}/api/tags", timeout=2).status_code == 200
        except requests.exceptions.RequestException:
            return False

    @staticmethod
    def _load_json(path: str) -> Dict:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    @staticmethod
    def _save_json(path: str, data: Dict):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)

    def _cache_key(self, text: str) -> str:
        """
        Content hash over the FULL text.

        A prefix or Python's salted hash() would collide across the overlapping
        chunks this pipeline produces and return the wrong vector.
        """
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"{self.backend}:{self.model}:{digest}"

    def _hash_embed(self, text: str) -> List[float]:
        """Deterministic bag-of-words vector, L2-normalised. No dependencies."""
        vec = [0.0] * HASH_DIMS
        for token in re.findall(r"\w+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            idx = int.from_bytes(digest[:4], "big") % HASH_DIMS
            sign = 1.0 if digest[4] % 2 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm else vec

    def _ollama_embed(self, text: str) -> List[float]:
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=60,
            )
            response.raise_for_status()
            return response.json()["embedding"]
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Lost connection to Ollama at {self.base_url}. Is `ollama serve` still running?"
            )

    def embed_text(self, text: str) -> List[float]:
        """Embed text, using the on-disk cache when possible."""
        key = self._cache_key(text)
        if key in self.cache:
            return self.cache[key]

        embedding = self._hash_embed(text) if self.backend == "hash" else self._ollama_embed(text)

        self.cache[key] = embedding
        self._pending_writes += 1
        if self._pending_writes >= 50:
            self.flush()
        return embedding

    def flush(self):
        """Persist cache and index. Called in batches to avoid O(n^2) disk writes."""
        if self._pending_writes:
            self._save_json(EMBEDDINGS_CACHE_PATH, self.cache)
            self._pending_writes = 0
        self._save_json(CORPUS_INDEX_PATH, self.corpus_index)

    def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Embed every chunk and record it in the corpus index."""
        result = []
        for chunk in chunks:
            result.append({**chunk, "embedding": self.embed_text(chunk["text"])})
            self.corpus_index[chunk["chunk_id"]] = {
                "doc_id": chunk["doc_id"],
                "doc_type": chunk["doc_type"],
                "position": chunk["position"],
                "word_count": chunk["word_count"],
            }
        self.flush()
        return result

    def get_corpus_metadata(self, chunk_id: str) -> Dict:
        return self.corpus_index.get(chunk_id, {})
