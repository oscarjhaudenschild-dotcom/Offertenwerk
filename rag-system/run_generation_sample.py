#!/usr/bin/env python3
"""
Answer-quality sample (the "G" in RAG): generate an answer for all 60 gold
questions in ONE setting and log everything needed for hand scoring.

Setting: confusable noise, 10 noise documents, k=20, one run. It reuses the
grid's retrieval unchanged, including the same random draw of noise documents,
so retrieval results can be compared with results_grid.csv row by row.

    export ANTHROPIC_API_KEY=...        (in the terminal only, never in a file)
    python3 run_generation_sample.py

Only ./corpus (anonymised) reaches the API, never roh/.
"""

import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from corpus_builder import CorpusBuilder
from gold_set import GoldSet
from measurement import CSV_FIELDS, MeasurementHarness
from rag_system import GENERATION_MAX_TOKENS, GENERATION_MODEL, RAGSystem

CORPUS_DIR = "./corpus"
GOLD_PATH = "./measurements/gold_set.json"
GRID_PATH = "./measurements/results_grid.csv"
OUT_PATH = Path("./measurements/generation_sample.csv")
SETTINGS_PATH = Path("./measurements/generation_sample_settings.json")

NOISE_MODE = "confusable"
NOISE_LEVEL = 10
GRID_LEVELS = [10, 50, 100, 200]  # noise is built for the largest level, as in the grid
K = 20
RUNS = 1
CHUNK_SIZE, OVERLAP = 400, 50

# Frozen before the run. Do not edit after the first look at results.
PROMPT = (
    "Du bist Experte für Schweizer Treuhand- und Rechnungswesen. "
    "Beantworte die Frage AUSSCHLIESSLICH auf Basis des bereitgestellten Kontexts. "
    "Antworte auf Deutsch, auch wenn die Frage auf Englisch gestellt ist, und knapp. "
    "Wenn der Kontext die Antwort nicht enthält, antworte exakt: "
    "'Die Information ist in den bereitgestellten Dokumenten nicht enthalten.'"
)

EXTRA_FIELDS = ["query", "expected_chunk_ids", "retrieved_chunk_texts"]


class FrozenPromptRAG(RAGSystem):
    def generate(self, query, retrieved_chunks, system_prompt=None):
        return super().generate(query, retrieved_chunks, system_prompt or PROMPT)


def protected_values(gold: GoldSet) -> set:
    """Figures the gold set expects; no distractor may state one by chance."""
    numbers = set()
    for case in gold.get_cases():
        for n in re.findall(r"[\d'’]+", case.get("expected_answer", "")):
            digits = n.replace("'", "").replace("’", "")
            if digits:
                numbers.add(int(digits))
    return numbers


def write_settings() -> None:
    SETTINGS_PATH.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "model": GENERATION_MODEL, "provider": "Anthropic API",
        "temperature": "Modellstandard (das Modell lehnt den Parameter temperature ab)",
        "max_tokens": GENERATION_MAX_TOKENS,
        "k": K, "noise_mode": NOISE_MODE, "noise_level": NOISE_LEVEL, "run": 1,
        "chunk_size": CHUNK_SIZE, "overlap": OVERLAP,
        "gold_set": GOLD_PATH, "prompt": PROMPT,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def compare_with_grid(results: list) -> None:
    """Retrieval must match the grid run for run, otherwise nothing is comparable."""
    with open(GRID_PATH, encoding="utf-8") as f:
        grid = {r["case_id"]: r["retrieved_chunk_ids"] for r in csv.DictReader(f)
                if r["noise_mode"] == NOISE_MODE and r["noise_level"] == str(NOISE_LEVEL)
                and r["k"] == str(K) and r["run"] == "1"}
    same = sum(grid.get(r["case_id"]) == r["retrieved_chunk_ids"] for r in results)
    print(f"Abruf identisch mit results_grid.csv: {same} von {len(results)} Fragen")
    if same != len(results):
        print("  ! Abweichung - Ergebnisse nicht mit Kapitel 4.3 vergleichbar, nicht bewerten.")


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY ist nicht gesetzt (nur im Terminal setzen). Abbruch.")
        return 1
    if OUT_PATH.exists() or SETTINGS_PATH.exists():
        print(f"{OUT_PATH} oder {SETTINGS_PATH} existiert schon. Nichts wird ueberschrieben.")
        return 1

    builder = CorpusBuilder(corpus_dir=CORPUS_DIR)
    builder.load_directory(CORPUS_DIR)
    base_docs = builder.get_documents()
    gold = GoldSet(path=GOLD_PATH)
    noise_docs = builder.build_noise(base_docs, max(GRID_LEVELS), mode=NOISE_MODE,
                                     protected_values=protected_values(gold))

    rag = FrozenPromptRAG(chunk_size=CHUNK_SIZE, overlap=OVERLAP, k=K, enable_generation=True)
    harness = MeasurementHarness(rag, gold, results_path=str(OUT_PATH), noise_mode=NOISE_MODE)

    write_settings()
    try:
        results = harness.run_experiment(base_docs, noise_docs, noise_levels=[NOISE_LEVEL], runs=RUNS)
    except BaseException:
        SETTINGS_PATH.unlink()  # a failed start must not block the next attempt
        raise

    if any(r["generation_skipped"] for r in results):
        print("Generierung wurde uebersprungen. Ergebnis verworfen.")
        return 1
    compare_with_grid(results)

    queries = {c["case_id"]: c for c in gold.get_cases()}
    chunk_text = {c["chunk_id"]: c["text"] for c in rag.corpus}
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS + EXTRA_FIELDS)
        writer.writeheader()
        for r in results:
            case = queries[r["case_id"]]
            ids = r["retrieved_chunk_ids"].split("|")
            writer.writerow({
                **{k: r.get(k, "") for k in CSV_FIELDS},
                "query": case["query"],
                "expected_chunk_ids": "|".join(case.get("expected_chunk_ids") or []),
                "retrieved_chunk_texts": json.dumps({i: chunk_text[i] for i in ids}, ensure_ascii=False),
            })
    print(f"{len(results)} Zeilen -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
