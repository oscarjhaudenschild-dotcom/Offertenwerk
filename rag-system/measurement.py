"""Measurement harness for the RAG scaling experiment."""

import csv
import os
import random
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from config import NOISE_LEVELS, VERBOSE
from gold_set import GoldSet
from rag_system import RAGSystem
from retrieval import RetrievalEvaluator

CSV_FIELDS = [
    "timestamp", "case_id", "category", "noise_mode", "noise_level",
    "corpus_chunks", "corpus_docs",
    "run", "retrieval_hit", "error_type", "unanswerable",
    "expected_document", "retrieved_documents",
    "kategorie", "expected_region", "top_region", "k", "content_hit",
    "retrieval_precision", "retrieval_recall",
    "chunks_retrieved", "chunks_expected",
    "top_similarity", "avg_similarity", "confusable_in_topk", "retrieved_chunk_ids",
    "tokens_in", "tokens_out",
    "retrieval_time_ms", "generation_time_ms", "total_time_ms",
    "embedding_backend", "generation_skipped", "expected_answer", "actual_answer", "quality_rating",
]


def classify_retrieval(retrieved: List[Dict], case: Dict) -> str:
    """
    Name the failure mode, not just whether it failed.

    The distinction that matters on a real corpus is between reaching into the
    wrong client's offer and reaching into the wrong passage of the right one.
    The first is a search problem, the second a chunking problem, and a single
    "missed" bucket would hide which of the two was actually measured.

    Unanswerable cases invert the test: there the correct behaviour is to find
    nothing convincing, so returning confident passages is itself the failure.
    """
    expected_ids = case.get("expected_chunk_ids") or []
    expected_doc = case.get("expected_document")
    unanswerable = case.get("unanswerable", False)

    if not retrieved:
        return "korrekt_abgelehnt" if unanswerable else "nichts_gefunden"

    if unanswerable:
        # No document holds the answer. Passages that still score highly are
        # exactly the material a generator would build a confident wrong
        # answer from.
        top = max(c.get("similarity", 0.0) for c in retrieved)
        return "material_fuer_halluzination" if top >= 0.60 else "korrekt_abgelehnt"

    if not expected_ids and not expected_doc:
        return "nicht_annotiert"

    ids = [c["chunk_id"] for c in retrieved]
    if expected_ids and set(ids) & set(expected_ids):
        return "richtig"

    sources = {c.get("doc_id") for c in retrieved}
    if expected_doc and expected_doc in sources:
        return "falsche_stelle"

    if any(c.get("doc_type") == "noise_confusable" for c in retrieved):
        return "fehlgriff_confusable"
    if any(str(c.get("doc_type", "")).startswith("noise") for c in retrieved):
        return "fehlgriff_unrelated"
    return "falsches_dokument"


class MeasurementHarness:
    """
    Run the scaling experiment: hold the base corpus constant, grow the noise.

    The base corpus carries the answers and must be present at every noise level;
    only the volume of irrelevant documents changes between runs.
    """

    def __init__(
        self,
        rag_system: RAGSystem,
        gold_set: GoldSet,
        results_path: str = "./measurements/results.csv",
        noise_mode: str = "unspecified",
    ):
        self.rag = rag_system
        self.gold_set = gold_set
        self.results_path = results_path
        self.noise_mode = noise_mode
        self.results: List[Dict] = []

    def run_experiment(
        self,
        base_docs: List[Tuple[str, str, str]],
        noise_docs: List[Tuple[str, str, str]],
        noise_levels: Optional[List[int]] = None,
        max_cases: Optional[int] = None,
        runs: int = 3,
        seed: int = 20260909,
    ) -> List[Dict]:
        """
        Run every gold case at every noise level, repeated `runs` times.

        Each repeat draws a different random subset of the noise documents. A
        single draw can be lucky or unlucky, and with a small gold set one
        fortunate composition would look like a result. Repeating makes the
        spread visible alongside the mean.
        """
        levels = noise_levels or NOISE_LEVELS
        cases = self.gold_set.get_cases()[:max_cases] if max_cases else self.gold_set.get_cases()

        if not cases:
            raise ValueError("Gold set is empty - nothing to measure.")
        if not base_docs:
            raise ValueError("Base corpus is empty - every case would score zero.")

        rng = random.Random(seed)

        for level in levels:
            if level > len(noise_docs):
                print(f"  ! only {len(noise_docs)} noise docs available, "
                      f"requested {level}; using all of them")

            for run in range(1, runs + 1):
                if level >= len(noise_docs):
                    available = list(noise_docs)
                else:
                    available = rng.sample(noise_docs, level)

                if VERBOSE:
                    print(f"\n=== noise level {level}, run {run}/{runs} "
                          f"({len(available)} noise docs) ===")

                # Base corpus is always present; only noise volume varies.
                self.rag.ingest_documents(base_docs + available, replace=True)

                for case in cases:
                    record = self._test_case(case, level)
                    record["run"] = run
                    self.results.append(record)
                if VERBOSE:
                    mark = "HIT " if record["retrieval_hit"] else "miss"
                    print(f"    {mark} {case['case_id']:<12} "
                          f"top={record['top_similarity']:.3f} "
                          f"{record['total_time_ms']:.0f}ms")

        return self.results

    def _test_case(self, case: Dict, noise_level: int) -> Dict:
        retrieved, retrieval_ms = self.rag.retrieve(case["query"])
        retrieved_ids = [c["chunk_id"] for c in retrieved]

        evaluation = RetrievalEvaluator.evaluate_retrieval(
            retrieved_ids, case.get("expected_chunk_ids", [])
        )
        generation = self.rag.generate(case["query"], retrieved)
        similarities = [c["similarity"] for c in retrieved]
        stats = self.rag.get_corpus_stats()

        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "case_id": case["case_id"],
            "category": case.get("category", "unknown"),
            "noise_mode": self.noise_mode,
            "noise_level": noise_level,
            "error_type": classify_retrieval(retrieved, case),
            "expected_document": case.get("expected_document", ""),
            "retrieved_documents": "|".join(
                dict.fromkeys(c.get("doc_id", "") for c in retrieved)
            ),
            "unanswerable": case.get("unanswerable", False),
            "kategorie": case.get("kategorie", ""),
            # Was the expected wording anywhere in what came back, regardless of
            # which document it came from? For a fact stated identically in 13
            # offers, insisting on one specific copy measures tie-breaking, not
            # retrieval - so both criteria are recorded and reported apart.
            "content_hit": bool(
                case.get("expected_answer")
                and any(case["expected_answer"].split(" -")[0] in c.get("text", "")
                        for c in retrieved)
            ),
            "k": self.rag.k,
            "expected_region": next(
                (c.get("region", "") for c in self.rag.corpus
                 if c.get("chunk_id") in (case.get("expected_chunk_ids") or [])), ""),
            "top_region": retrieved[0].get("region", "") if retrieved else "",
            "confusable_in_topk": sum(
                1 for c in retrieved if c.get("doc_type") == "noise_confusable"
            ),
            "corpus_chunks": stats["chunk_count"],
            "corpus_docs": stats["doc_count"],
            "retrieval_hit": evaluation["hit"],
            "retrieval_precision": round(evaluation["precision"], 4),
            "retrieval_recall": round(evaluation["recall"], 4),
            "chunks_retrieved": evaluation["num_retrieved"],
            "chunks_expected": evaluation["num_expected"],
            "top_similarity": round(max(similarities), 4) if similarities else 0.0,
            "avg_similarity": round(sum(similarities) / len(similarities), 4) if similarities else 0.0,
            "retrieved_chunk_ids": "|".join(retrieved_ids),
            "tokens_in": generation["tokens_in"],
            "tokens_out": generation["tokens_out"],
            "retrieval_time_ms": round(retrieval_ms, 2),
            "generation_time_ms": round(generation["generation_time_ms"], 2),
            "total_time_ms": round(retrieval_ms + generation["generation_time_ms"], 2),
            "embedding_backend": self.rag.embeddings.backend,
            "generation_skipped": generation["skipped"],
            "expected_answer": case.get("expected_answer", ""),
            "actual_answer": generation["answer"] or "",
            "quality_rating": "",
        }

    def save_results(self):
        if not self.results:
            print("No results to save.")
            return
        os.makedirs(os.path.dirname(self.results_path) or ".", exist_ok=True)
        with open(self.results_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in self.results:
                writer.writerow({k: record.get(k, "") for k in CSV_FIELDS})
        print(f"\nResults written to {self.results_path} ({len(self.results)} rows)")

    def print_summary(self):
        if not self.results:
            return
        print("\n" + "=" * 62)
        print("SUMMARY")
        print("=" * 62)
        print(f"{'Noise':>7} {'Cases':>7} {'Hit rate':>10} {'Recall':>9} {'Top sim':>9} {'Time ms':>9}")
        print("-" * 62)
        for level in sorted({r["noise_level"] for r in self.results}):
            rows = [r for r in self.results if r["noise_level"] == level]
            hit_rate = sum(r["retrieval_hit"] for r in rows) / len(rows)
            recall = sum(r["retrieval_recall"] for r in rows) / len(rows)
            top_sim = sum(r["top_similarity"] for r in rows) / len(rows)
            avg_ms = sum(r["total_time_ms"] for r in rows) / len(rows)
            print(f"{level:>7} {len(rows):>7} {hit_rate:>9.1%} {recall:>9.2f} "
                  f"{top_sim:>9.3f} {avg_ms:>9.0f}")

        errors = [r["error_type"] for r in self.results if r["error_type"] != "hit"]
        if errors:
            print("\nFailure modes:")
            for name in sorted(set(errors)):
                count = errors.count(name)
                label = {
                    "fehlgriff_confusable": "wrong-but-plausible source (dangerous)",
                    "fehlgriff_unrelated": "irrelevant source",
                    "miss_other_source": "missed, no noise retrieved",
                    "no_expectation": "gold case not annotated",
                }.get(name, name)
                print(f"  {count:>4}  {name:<22} {label}")

        if all(r["chunks_expected"] == 0 for r in self.results):
            print("\n! Every case has expected_chunk_ids = [], so hit rate is")
            print("  meaningless. Annotate the gold set before the real run.")
