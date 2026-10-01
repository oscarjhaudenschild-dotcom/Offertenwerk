#!/usr/bin/env python3
"""
Analyze experiment results: plot curves, compute statistics, find crossover point.

Usage:
    python analyze_results.py [--csv measurements/results.csv] [--output plots/]
"""

import csv
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple
import statistics


class ResultsAnalyzer:
    """Parse and analyze CSV results from measurement harness."""

    def __init__(self, csv_path: str = "measurements/results.csv"):
        self.csv_path = csv_path
        self.results = []
        self.by_noise_level = defaultdict(list)
        self.by_case = defaultdict(list)

    def load_results(self) -> bool:
        """Load CSV results into memory."""
        if not Path(self.csv_path).exists():
            print(f"✗ File not found: {self.csv_path}")
            return False

        try:
            with open(self.csv_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric fields
                    try:
                        row["noise_level"] = int(row["noise_level"])
                        row["retrieval_hit"] = row["retrieval_hit"].lower() == "true"
                        row["retrieval_precision"] = float(row.get("retrieval_precision", 0))
                        row["retrieval_recall"] = float(row.get("retrieval_recall", 0))
                        row["top_similarity"] = float(row.get("top_similarity", 0))
                        row["avg_similarity"] = float(row.get("avg_similarity", 0))
                        row["tokens_in"] = int(row.get("tokens_in") or 0)
                        row["tokens_generated"] = int(row.get("tokens_out") or 0)
                        row["generation_time_ms"] = float(row.get("generation_time_ms", 0))
                        row["retrieval_time_ms"] = float(row.get("retrieval_time_ms", 0))
                        row["total_time_ms"] = float(row.get("total_time_ms", 0))
                    except (ValueError, KeyError):
                        continue

                    self.results.append(row)
                    self.by_noise_level[row["noise_level"]].append(row)
                    self.by_case[row["case_id"]].append(row)

            print(f"✓ Loaded {len(self.results)} results from {self.csv_path}")
            return True

        except Exception as e:
            print(f"✗ Error reading CSV: {e}")
            return False

    def compute_summary_stats(self) -> Dict:
        """Compute summary statistics by noise level."""
        stats = {}

        for noise_level in sorted(self.by_noise_level.keys()):
            records = self.by_noise_level[noise_level]

            hit_rate = sum(1 for r in records if r["retrieval_hit"]) / len(records) if records else 0
            precisions = [r["retrieval_precision"] for r in records if r["retrieval_precision"]]
            recalls = [r["retrieval_recall"] for r in records if r["retrieval_recall"]]
            similarities = [r["avg_similarity"] for r in records if r["avg_similarity"]]
            tokens = [r["tokens_generated"] for r in records if r["tokens_generated"]]
            times = [r["total_time_ms"] for r in records if r["total_time_ms"]]

            stats[noise_level] = {
                "count": len(records),
                "hit_rate": hit_rate,
                "avg_precision": statistics.mean(precisions) if precisions else 0,
                "avg_recall": statistics.mean(recalls) if recalls else 0,
                "avg_similarity": statistics.mean(similarities) if similarities else 0,
                "avg_tokens": statistics.mean(tokens) if tokens else 0,
                "avg_time_ms": statistics.mean(times) if times else 0,
            }

        return stats

    def print_summary(self):
        """Print summary table."""
        if not self.results:
            print("No results to analyze")
            return

        stats = self.compute_summary_stats()

        print("\n" + "=" * 100)
        print("EXPERIMENT SUMMARY")
        print("=" * 100)
        print()
        print(f"{'Noise':<8} {'Count':<8} {'Hit %':<10} {'Precision':<12} {'Recall':<12} {'Similarity':<12} {'Tokens':<10} {'Time (ms)':<12}")
        print("-" * 100)

        for noise_level in sorted(stats.keys()):
            s = stats[noise_level]
            print(
                f"{noise_level:<8} {s['count']:<8} {s['hit_rate']*100:>8.1f}% {s['avg_precision']:>11.2f} "
                f"{s['avg_recall']:>11.2f} {s['avg_similarity']:>11.3f} {s['avg_tokens']:>9.0f} {s['avg_time_ms']:>11.0f}"
            )

        print()

    def print_case_summary(self):
        """Print per-case performance across noise levels."""
        if not self.results:
            return

        print("\n" + "=" * 80)
        print("PER-CASE PERFORMANCE")
        print("=" * 80)
        print()

        cases_to_show = sorted(set(r["case_id"] for r in self.results))[:5]  # Top 5

        for case_id in cases_to_show:
            records = self.by_case[case_id]
            print(f"\n{case_id}:")
            print(f"  {'Noise':<8} {'Hit':<6} {'Precision':<12} {'Recall':<12}")
            print(f"  {'-' * 40}")

            for record in sorted(records, key=lambda r: r["noise_level"]):
                hit = "✓" if record["retrieval_hit"] else "✗"
                print(
                    f"  {record['noise_level']:<8} {hit:<6} {record['retrieval_precision']:>11.2f} {record['retrieval_recall']:>11.2f}"
                )

    def detect_degradation(self) -> Dict:
        """Find where quality starts degrading significantly."""
        stats = self.compute_summary_stats()
        noise_levels = sorted(stats.keys())

        if len(noise_levels) < 2:
            return {}

        degradation = {}
        baseline_hit_rate = stats[noise_levels[0]]["hit_rate"]

        for noise_level in noise_levels[1:]:
            hit_rate = stats[noise_level]["hit_rate"]
            degradation[noise_level] = {
                "hit_rate": hit_rate,
                "drop_from_baseline": baseline_hit_rate - hit_rate,
                "percent_drop": (baseline_hit_rate - hit_rate) / baseline_hit_rate * 100 if baseline_hit_rate > 0 else 0
            }

        return degradation

    def print_degradation_analysis(self):
        """Print degradation analysis."""
        degradation = self.detect_degradation()

        if not degradation:
            return

        print("\n" + "=" * 80)
        print("QUALITY DEGRADATION ANALYSIS")
        print("=" * 80)
        print()
        print(f"{'Noise':<10} {'Hit Rate':<15} {'Drop':<15} {'% Drop':<12}")
        print("-" * 60)

        for noise_level in sorted(degradation.keys()):
            d = degradation[noise_level]
            print(
                f"{noise_level:<10} {d['hit_rate']*100:>13.1f}% {d['drop_from_baseline']:>13.1%} {d['percent_drop']:>10.1f}%"
            )

    def estimate_crossover(self) -> Dict:
        """
        Estimate where RAG performance might fall below Long-Context.

        Very rough heuristic: if hit_rate < 50%, RAG is struggling.
        """
        stats = self.compute_summary_stats()

        crossover = None
        for noise_level in sorted(stats.keys()):
            if stats[noise_level]["hit_rate"] < 0.5:
                crossover = noise_level
                break

        return {
            "crossover_noise_level": crossover,
            "note": "Hit rate < 50% suggests retrieval breakdown"
        }

    def print_recommendations(self):
        """Print recommendations based on results."""
        if not self.results:
            return

        degradation = self.detect_degradation()
        stats = self.compute_summary_stats()

        print("\n" + "=" * 80)
        print("RECOMMENDATIONS FOR THESIS")
        print("=" * 80)
        print()

        # Degradation pattern
        if degradation:
            worst_drop = max(degradation.values(), key=lambda x: x["percent_drop"])
            print(f"1. Worst degradation: {worst_drop['percent_drop']:.1f}% drop between noise levels")

        # Performance characterization
        baseline_hit_rate = list(sorted(stats.keys()))[0]
        if stats[baseline_hit_rate]["hit_rate"] > 0.85:
            print("2. RAG performs very well at low noise (baseline hit >85%)")
        elif stats[baseline_hit_rate]["hit_rate"] > 0.70:
            print("2. RAG performs reasonably at low noise (baseline hit >70%)")
        else:
            print("2. Warning: RAG struggles even at baseline (hit <70%) — check chunking/embedding")

        # Cost analysis
        baseline_tokens = stats[baseline_hit_rate]["avg_tokens"]
        print(f"3. Average tokens per query: {baseline_tokens:.0f}")
        print(f"   Estimated cost per query: ${baseline_tokens * 0.0001:.4f} (rough)")

        print()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze RAG experiment results")
    parser.add_argument("--csv", default="measurements/results.csv", help="Path to results CSV")
    parser.add_argument("--output", default="plots/", help="Output directory for plots")

    args = parser.parse_args()

    analyzer = ResultsAnalyzer(args.csv)

    if not analyzer.load_results():
        sys.exit(1)

    analyzer.print_summary()
    analyzer.print_case_summary()
    analyzer.print_degradation_analysis()
    print()
    crossover = analyzer.estimate_crossover()
    if crossover["crossover_noise_level"]:
        print(f"⚠ Estimated crossover point: noise level {crossover['crossover_noise_level']}")
    else:
        print("✓ No significant degradation detected across noise levels")

    analyzer.print_recommendations()

    print("\n✓ Analysis complete")


if __name__ == "__main__":
    main()
