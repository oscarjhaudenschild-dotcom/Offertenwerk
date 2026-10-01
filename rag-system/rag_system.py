"""Main RAG system orchestrator."""

import os
import time
from typing import Dict, List, Optional, Tuple

from config import K_TOP_RESULTS
from retrieval_core import RetrievalCore

GENERATION_MODEL = "claude-opus-5"
# Generous on purpose: the model may spend tokens on internal thinking before
# it answers, and a cut-off answer must never be scored as a wrong one.
GENERATION_MAX_TOKENS = 4000

SYSTEM_PROMPT = (
    "Du bist Experte für Schweizer Treuhand- und Rechnungswesen. "
    "Beantworte die Frage AUSSCHLIESSLICH auf Basis des bereitgestellten Kontexts. "
    "Wenn der Kontext die Antwort nicht enthält, antworte exakt: "
    "'Die Information ist in den bereitgestellten Dokumenten nicht enthalten.'"
)


class RAGSystem:
    """
    RAG pipeline: ingest -> chunk -> embed -> retrieve -> (optionally) generate.

    Generation is optional on purpose. Retrieval hit rate is measurable without
    any LLM, and it is the diagnostic metric the experiment depends on, so the
    harness must run with no API key and no network.
    """

    def __init__(
        self,
        chunk_size: int = 400,
        overlap: int = 50,
        k: int = K_TOP_RESULTS,
        embedding_backend: str = "auto",
        enable_generation: bool = True,
        strip_letterhead: bool = False,
    ):
        # Retrieval lives in RetrievalCore so the offer tool and this harness
        # share one implementation rather than two that drift apart.
        self.core = RetrievalCore(
            chunk_size=chunk_size, overlap=overlap, k=k,
            embedding_backend=embedding_backend, strip_letterhead=strip_letterhead,
        )
        self.k = k
        self.enable_generation = enable_generation
        self._claude = None

    # Kept as properties: measurement.py and the CLI read these directly.
    @property
    def corpus(self) -> List[Dict]:
        return self.core.corpus

    @property
    def chunker(self):
        return self.core.chunker

    @property
    def embeddings(self):
        return self.core.embeddings

    @property
    def claude(self):
        """Lazy client so the pipeline imports and runs without anthropic installed."""
        if self._claude is None:
            try:
                import anthropic
            except ImportError:
                raise RuntimeError(
                    "The anthropic package is required for generation. "
                    "Install it with `pip install anthropic`, or run with "
                    "enable_generation=False to measure retrieval only."
                )
            self._claude = anthropic.Anthropic()
        return self._claude

    def ingest_documents(self, documents: List[Tuple[str, str, str]], replace: bool = True):
        """
        Chunk and embed documents.

        replace=True resets the corpus first. The scaling experiment rebuilds the
        corpus at every noise level, so leaving stale chunks in place would make
        each level cumulative and invalidate the measurements.
        """
        self.core.ingest_documents(documents, replace=replace)

    def retrieve(self, query: str) -> Tuple[List[Dict], float]:
        """Retrieve top-k chunks. Returns (chunks, elapsed_ms)."""
        return self.core.search(query)

    def generate(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        system_prompt: Optional[str] = None,
    ) -> Dict:
        """Generate an answer from the retrieved chunks."""
        # A missing key means generation is unavailable, not that the run is
        # broken. Retrieval is the measurement the experiment depends on, and
        # it must not be lost because no key happens to be set.
        if self.enable_generation and not os.environ.get("ANTHROPIC_API_KEY"):
            self.enable_generation = False
            print("  ! ANTHROPIC_API_KEY nicht gesetzt - nur Abruf wird gemessen.")

        if not self.enable_generation:
            return {
                "answer": None,
                "tokens_in": 0,
                "tokens_out": 0,
                "used_chunks": [c["chunk_id"] for c in retrieved_chunks],
                "generation_time_ms": 0.0,
                "skipped": True,
            }

        start = time.perf_counter()
        context = "\n\n".join(f"[{c['chunk_id']}]\n{c['text']}" for c in retrieved_chunks)
        response = self.claude.messages.create(
            model=GENERATION_MODEL,
            max_tokens=GENERATION_MAX_TOKENS,
            system=system_prompt or SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Kontext:\n{context}\n\nFrage: {query}"}],
        )
        if response.stop_reason == "max_tokens":
            raise RuntimeError("Answer was cut off at the token limit; raise GENERATION_MAX_TOKENS.")
        # Thinking blocks come first on some models; only the text blocks are the answer.
        answer = "".join(block.text for block in response.content if block.type == "text")
        return {
            "answer": answer,
            "tokens_in": response.usage.input_tokens,
            "tokens_out": response.usage.output_tokens,
            "used_chunks": [c["chunk_id"] for c in retrieved_chunks],
            "generation_time_ms": (time.perf_counter() - start) * 1000,
            "skipped": False,
        }

    def query(self, query: str) -> Dict:
        """End-to-end query with diagnostics."""
        retrieved, retrieval_ms = self.retrieve(query)
        generation = self.generate(query, retrieved)
        return {
            "query": query,
            "retrieved_chunks": [
                {
                    "chunk_id": c["chunk_id"],
                    "similarity": c["similarity"],
                    "doc_id": c["doc_id"],
                    "doc_type": c["doc_type"],
                }
                for c in retrieved
            ],
            "answer": generation["answer"],
            "tokens_in": generation["tokens_in"],
            "tokens_out": generation["tokens_out"],
            "retrieval_time_ms": retrieval_ms,
            "generation_time_ms": generation["generation_time_ms"],
            "corpus_size": len(self.corpus),
        }

    def get_corpus_stats(self) -> Dict:
        if not self.corpus:
            return {"chunk_count": 0, "doc_count": 0, "avg_chunk_size": 0}
        return {
            "chunk_count": len(self.corpus),
            "doc_count": len({c.get("doc_id") for c in self.corpus}),
            "avg_chunk_size": sum(c.get("word_count", 0) for c in self.corpus) / len(self.corpus),
        }
