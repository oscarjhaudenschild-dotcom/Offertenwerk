#!/usr/bin/env python3
"""
Run the RAG scaling experiment.

Examples:
    python3 run_experiment.py --bootstrap --offline --quick
    python3 run_experiment.py --noise-levels 10,50,100,200
"""

import argparse
import re
import sys

from config import NOISE_LEVELS
from corpus_builder import CorpusBuilder
from gold_set import GoldSet
from measurement import MeasurementHarness
from rag_system import RAGSystem


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run the RAG scaling experiment")
    p.add_argument("--bootstrap", action="store_true",
                   help="use the built-in demo corpus instead of ./corpus")
    p.add_argument("--offline", action="store_true",
                   help="hash embeddings + no generation; tests the pipeline with no Ollama or API key")
    p.add_argument("--quick", action="store_true",
                   help="2 cases, noise levels 10 and 50")
    p.add_argument("--noise-levels", type=str, default=None,
                   help="comma separated, e.g. 10,50,100,200")
    p.add_argument("--chunk-size", type=int, default=400, help="words per chunk")
    p.add_argument("--overlap", type=int, default=50, help="word overlap between chunks")
    p.add_argument("--k", type=int, default=3, help="chunks to retrieve")
    p.add_argument("--corpus-dir", type=str, default="./corpus")
    p.add_argument("--noise-mode", choices=["unrelated", "confusable", "mixed"],
                   default="confusable",
                   help="unrelated=different topics; confusable=superseded price lists "
                        "(default, the case that stresses retrieval); mixed=both")
    p.add_argument("--out", type=str, default="./measurements/results.csv")
    p.add_argument("--runs", type=int, default=3,
                   help="repeats per noise level with a different random draw")
    p.add_argument("--strip-letterhead", action="store_true",
                   help="drop the name/address/greeting block before chunking "
                        "(comparison run; the practitioner tool never sets this)")
    p.add_argument("--gold-set", type=str, default="./measurements/gold_set.json",
                   help="expected_chunk_ids must be built against the same "
                        "chunking that's being measured, so the stripped run "
                        "needs its own gold set (see build_gold_set.py "
                        "--strip-letterhead)")
    return p


def main() -> int:
    args = build_parser().parse_args()

    if args.noise_levels:
        try:
            levels = [int(x) for x in args.noise_levels.split(",") if x.strip()]
        except ValueError:
            print("--noise-levels must be integers, e.g. 10,50,100")
            return 1
    else:
        levels = NOISE_LEVELS

    max_cases = None
    if args.quick:
        levels, max_cases = [10, 50], 2

    print("=" * 62)
    print("RAG SCALING EXPERIMENT")
    print("=" * 62)
    print(f"chunk size {args.chunk_size}w / overlap {args.overlap}w / k={args.k}")
    print(f"noise levels: {levels}")
    print(f"mode: {'OFFLINE (pipeline test only)' if args.offline else 'full'}")
    print()

    builder = CorpusBuilder(corpus_dir=args.corpus_dir)
    if args.bootstrap:
        base_docs = CorpusBuilder.create_bootstrap_corpus()
        print(f"corpus: bootstrap ({len(base_docs)} docs)")
    else:
        builder.load_directory(args.corpus_dir)
        base_docs = builder.get_documents()
        if not base_docs:
            print(f"No .txt files in {args.corpus_dir}. Use --bootstrap to try the pipeline.")
            return 1
        print(f"corpus: {len(base_docs)} docs from {args.corpus_dir}")

    gold = GoldSet(path=args.gold_set)
    if not gold.get_cases():
        for case in GoldSet.create_bootstrap_gold_set():
            gold.add_case(**case)
        print(f"gold set: created bootstrap ({len(gold.get_cases())} cases)")
    else:
        print(f"gold set: {len(gold.get_cases())} cases")

    # Every figure the gold set expects is protected, so no distractor can
    # state a correct answer by chance and turn a wrong-document retrieval into
    # an accidentally right one.
    protected = set()
    for case in gold.get_cases():
        protected.update(int(n.replace("'", "").replace("\u2019", ""))
                         for n in re.findall(r"[\d'\u2019]+", case.get("expected_answer", ""))
                         if n.strip("'\u2019"))
    noise_docs = builder.build_noise(base_docs, max(levels), mode=args.noise_mode,
                                     protected_values=protected)
    print(f"noise: {len(noise_docs)} documents, mode '{args.noise_mode}'")

    try:
        rag = RAGSystem(
            chunk_size=args.chunk_size,
            overlap=args.overlap,
            k=args.k,
            embedding_backend="hash" if args.offline else "auto",
            enable_generation=not args.offline,
            strip_letterhead=args.strip_letterhead,
        )
    except RuntimeError as exc:
        print(f"\nCould not start: {exc}")
        return 1

    harness = MeasurementHarness(rag, gold, results_path=args.out, noise_mode=args.noise_mode)
    try:
        harness.run_experiment(base_docs, noise_docs, noise_levels=levels,
                           max_cases=max_cases, runs=args.runs)
    except (ValueError, RuntimeError) as exc:
        print(f"\nExperiment stopped: {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted - saving partial results.")
        harness.save_results()
        return 130

    harness.save_results()
    harness.print_summary()
    return 0


if __name__ == "__main__":
    sys.exit(main())
