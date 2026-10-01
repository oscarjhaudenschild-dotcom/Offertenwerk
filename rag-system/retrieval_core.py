"""
The retrieval core shared by the measurement rig and the offer tool.

Both callers reach the same code: `rag.py experiment` measures it, and
`server.py` serves it to the sidebar in app.html. That is the point of this
module - the retrieval a practitioner uses is the retrieval the thesis
measures, not a second implementation that merely resembles it.

Two entry points, deliberately different:

  RetrievalCore.search()  returns chunks in the internal shape, unchanged, so
                          the measurement harness keeps working byte for byte.

  RetrievalCore.find()    returns a stable public shape (text, source document,
                          score) for anything outside this package.

The cosine similarity itself stays hand-written in retrieval.py.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from chunking import DocumentChunker
from config import K_TOP_RESULTS, VERBOSE
from embeddings import EmbeddingManager
from retrieval import CosineSimilaritySearch


class RetrievalCore:
    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 50,
        k: int = K_TOP_RESULTS,
        embedding_backend: str = "auto",
        strip_letterhead: bool = False,
    ):
        self.chunker = DocumentChunker(chunk_size=chunk_size, overlap=overlap,
                                       strip_letterhead=strip_letterhead)
        self.embeddings = EmbeddingManager(backend=embedding_backend)
        self.k = k
        self.corpus: List[Dict] = []
        # Directory fingerprint, so a long-running server reloads only when a
        # file actually changed instead of re-embedding on every request.
        self._loaded_from: Optional[Path] = None
        self._fingerprint: Optional[tuple] = None

    def ingest_documents(self, documents: List[Tuple[str, str, str]],
                         replace: bool = True) -> None:
        """
        Chunk and embed documents given as (doc_id, text, doc_type) tuples.

        replace=True resets the corpus first. The scaling experiment rebuilds
        the corpus at every noise level, so leaving stale chunks in place would
        make each level cumulative and invalidate the measurements.
        """
        if replace:
            self.corpus = []
        chunks = self.chunker.chunk_batch(documents)
        self.corpus.extend(self.embeddings.embed_chunks(chunks))
        if VERBOSE:
            print(f"    ingested {len(documents)} docs -> {len(chunks)} chunks "
                  f"(corpus now {len(self.corpus)})")

    @staticmethod
    def _fingerprint_dir(directory: Path) -> tuple:
        return tuple(sorted(
            (p.name, p.stat().st_mtime_ns, p.stat().st_size)
            for p in directory.glob("*.txt")
        ))

    def load_directory(self, directory: str, force: bool = False) -> int:
        """
        Load every .txt in a directory, skipping the work when nothing changed.

        Returns the number of chunks now held.
        """
        path = Path(directory)
        if not path.is_dir():
            raise FileNotFoundError(f"corpus directory not found: {directory}")

        fingerprint = self._fingerprint_dir(path)
        if not force and self._loaded_from == path and self._fingerprint == fingerprint:
            return len(self.corpus)

        documents = []
        for file in sorted(path.glob("*.txt")):
            text = file.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                # chunk_batch takes (text, doc_id, doc_type) in that order.
                documents.append((text, file.stem, "offer"))

        self.ingest_documents(documents, replace=True)
        self._loaded_from = path
        self._fingerprint = fingerprint
        return len(self.corpus)

    def search(self, query: str, k: Optional[int] = None) -> Tuple[List[Dict], float]:
        """
        Internal shape, unchanged: (chunks, elapsed_ms).

        The measurement harness reads chunk_id, similarity and doc_type off
        these dicts, so this return value must not be reshaped.
        """
        start = time.perf_counter()
        query_embedding = self.embeddings.embed_text(query)
        results = CosineSimilaritySearch.search(
            query_embedding, self.corpus, k=k or self.k
        )
        return results, (time.perf_counter() - start) * 1000

    def find(self, query: str, k: Optional[int] = None) -> List[Dict]:
        """Public shape for callers outside this package."""
        results, elapsed = self.search(query, k=k)
        return [
            {
                "chunk_text": c.get("text", ""),
                "source_document": c.get("doc_id", ""),
                "chunk_id": c.get("chunk_id", ""),
                "score": round(float(c.get("similarity", 0.0)), 4),
                "elapsed_ms": round(elapsed, 1),
            }
            for c in results
        ]


_shared: Dict[str, RetrievalCore] = {}


def search(query_text: str, corpus_dir: str, k: int = K_TOP_RESULTS) -> List[Dict]:
    """
    One-call retrieval against a corpus directory.

    Keeps one loaded core per directory, so repeated calls from a running
    server do not re-embed the corpus every time.
    """
    core = _shared.get(corpus_dir)
    if core is None:
        core = RetrievalCore()
        _shared[corpus_dir] = core
    core.load_directory(corpus_dir)
    return core.find(query_text, k=k)
