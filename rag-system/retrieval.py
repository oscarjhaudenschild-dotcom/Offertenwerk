"""Retrieval search using manually-implemented cosine similarity."""

import math
from typing import List, Dict, Tuple
from config import K_TOP_RESULTS, SIMILARITY_THRESHOLD


class CosineSimilaritySearch:
    """
    Manually-implemented cosine similarity search for RAG retrieval.

    This is intentionally written from scratch (not using sklearn/scipy) so the
    measurement logic is transparent and understandable for the thesis.
    """

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        cosine_similarity = (A · B) / (||A|| * ||B||)

        Returns a value between -1 and 1 (typically 0 to 1 for embeddings).
        """
        if not vec_a or not vec_b:
            return 0.0

        # Dot product: A · B
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))

        # Norms: ||A|| and ||B||
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    @staticmethod
    def search(
        query_embedding: List[float],
        corpus_embeddings: List[Dict],
        k: int = K_TOP_RESULTS,
        threshold: float = SIMILARITY_THRESHOLD
    ) -> List[Dict]:
        """
        Find top-k most similar chunks to query.

        Args:
            query_embedding: embedding vector of the query
            corpus_embeddings: list of dicts with 'chunk_id', 'embedding', 'text'
            k: number of top results to return
            threshold: minimum similarity score to include

        Returns:
            list of retrieved chunks, sorted by similarity (highest first)
        """
        scores = []

        # Compute similarity for every chunk
        for chunk in corpus_embeddings:
            similarity = CosineSimilaritySearch.cosine_similarity(
                query_embedding,
                chunk["embedding"]
            )

            if similarity >= threshold:
                scores.append({
                    "chunk_id": chunk["chunk_id"],
                    "text": chunk["text"],
                    "similarity": similarity,
                    "doc_id": chunk.get("doc_id", "unknown"),
                    "doc_type": chunk.get("doc_type", "unknown"),
                    "region": chunk.get("region", ""),
                })

        # Sort by similarity (descending) and return top-k
        scores.sort(key=lambda x: x["similarity"], reverse=True)
        return scores[:k]


class RetrievalEvaluator:
    """Evaluate retrieval quality against a gold standard."""

    @staticmethod
    def evaluate_retrieval(
        retrieved_chunk_ids: List[str],
        expected_chunk_ids: List[str]
    ) -> Dict:
        """
        Measure retrieval quality.

        Returns:
            - hit: True if any expected chunk was retrieved
            - precision: % of retrieved that were expected
            - recall: % of expected that were retrieved
            - found_ids: which expected chunks were found
        """
        retrieved_set = set(retrieved_chunk_ids)
        expected_set = set(expected_chunk_ids)

        found = retrieved_set & expected_set
        precision = len(found) / len(retrieved_set) if retrieved_set else 0.0
        recall = len(found) / len(expected_set) if expected_set else 0.0

        return {
            "hit": len(found) > 0,
            "precision": precision,
            "recall": recall,
            "found_ids": list(found),
            "num_expected": len(expected_set),
            "num_retrieved": len(retrieved_set)
        }
