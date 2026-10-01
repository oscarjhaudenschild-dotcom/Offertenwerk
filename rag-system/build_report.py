#!/usr/bin/env python3
"""
Turn results CSVs into tables for Kapitel 4.3 of the Maturaarbeit.

Writes measurements/report.md. Reads every measurements/results*.csv it finds,
so the noise designs appear side by side.
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

MEASUREMENTS = Path("measurements")
REPORT = MEASUREMENTS / "report.md"

ERROR_LABELS = {
    "richtig": "richtig",
    "falsche_stelle": "richtiges Dokument, falsche Stelle",
    "falsches_dokument": "falsches Dokument",
    "fehlgriff_confusable": "Fehlgriff auf verwechselbare Quelle",
    "fehlgriff_unrelated": "Fehlgriff auf unverwandte Quelle",
    "nichts_gefunden": "nichts gefunden",
    "material_fuer_halluzination": "unbeantwortbar, trotzdem Material geliefert",
    "korrekt_abgelehnt": "unbeantwortbar, korrekt nichts geliefert",
    "nicht_annotiert": "Testfall nicht annotiert",
}


def load_rows() -> List[Dict]:
    rows = []
    for path in sorted(MEASUREMENTS.glob("results*.csv")):
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Skip files written before noise_mode/error_type existed, rather
            # than showing them as a phantom column of unknown failures.
            if not reader.fieldnames or "error_type" not in reader.fieldnames:
                print(f"  uebersprungen (altes Format): {path.name}")
                continue
            for row in reader:
                try:
                    row["noise_level"] = int(row["noise_level"])
                    row["hit"] = row["retrieval_hit"].strip().lower() == "true"
                    row["retrieval_time_ms"] = float(row["retrieval_time_ms"])
                    row["corpus_chunks"] = int(row["corpus_chunks"])
                except (KeyError, ValueError):
                    continue
                row.setdefault("noise_mode", path.stem.replace("results_", ""))
                rows.append(row)
    return rows


def table_hit_rate(rows: List[Dict]) -> str:
    """
    Mean across repeats, with the spread between them.

    A single composition of noise documents can be lucky. Reporting only the
    mean would hide how much of the curve is the design and how much is the
    draw.
    """
    modes = sorted({r["noise_mode"] for r in rows})
    levels = sorted({r["noise_level"] for r in rows})
    answerable = [r for r in rows if str(r.get("unanswerable", "")).lower() != "true"]

    out = ["| Dokumente | " + " | ".join(f"{m} (Mittel ± Streuung)" for m in modes) + " |",
           "|---:|" + "---:|" * len(modes)]
    for level in levels:
        cells = []
        for mode in modes:
            per_run = []
            runs = sorted({r.get("run", "1") for r in answerable})
            for run in runs:
                subset = [r for r in answerable
                          if r["noise_mode"] == mode and r["noise_level"] == level
                          and r.get("run", "1") == run]
                if subset:
                    per_run.append(sum(r["hit"] for r in subset) / len(subset))
            if not per_run:
                cells.append("-")
            elif len(per_run) > 1:
                sd = statistics.stdev(per_run)
                cells.append(f"{statistics.mean(per_run):.1%} ± {sd:.1%}")
            else:
                cells.append(f"{per_run[0]:.1%}")
        out.append(f"| {level} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def table_errors(rows: List[Dict]) -> str:
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        counts[r["noise_mode"]][r.get("error_type", "unbekannt")] += 1
    modes = sorted(counts)
    kinds = sorted({k for m in counts.values() for k in m})
    out = ["| Fehlerart | " + " | ".join(modes) + " |", "|---|" + "---:|" * len(modes)]
    for kind in kinds:
        label = ERROR_LABELS.get(kind, kind)
        out.append(f"| {label} | " + " | ".join(str(counts[m][kind]) for m in modes) + " |")
    return "\n".join(out)


def table_latency(rows: List[Dict]) -> str:
    levels = sorted({r["noise_level"] for r in rows})
    out = ["| Dokumente | Chunks | Suchzeit (ms) |", "|---:|---:|---:|"]
    for level in levels:
        subset = [r for r in rows if r["noise_level"] == level]
        chunks = sum(r["corpus_chunks"] for r in subset) / len(subset)
        ms = sum(r["retrieval_time_ms"] for r in subset) / len(subset)
        out.append(f"| {level} | {chunks:.0f} | {ms:.1f} |")
    return "\n".join(out)


def main() -> int:
    rows = load_rows()
    if not rows:
        print(f"Keine Ergebnisse in {MEASUREMENTS}/results*.csv")
        print("Zuerst ausfuehren:  python3 rag.py experiment")
        return 1

    backends = {r.get("embedding_backend", "") for r in rows} - {""}
    hash_embeddings = "hash" in backends
    no_generation = any(str(r.get("generation_skipped", "")).lower() == "true" for r in rows)
    cases = len({r["case_id"] for r in rows})
    unanswerable = len({r["case_id"] for r in rows
                        if str(r.get("unanswerable", "")).lower() == "true"})
    runs = len({r.get("run", "1") for r in rows})

    parts = [
        "# Messergebnisse RAG-Prototyp",
        "",
        f"Grundlage: {len(rows)} Messungen, {cases} Testfaelle "
        f"(davon {unanswerable} unbeantwortbar), {runs} Laeufe je Stufe, "
        f"Rauschstufen {sorted({r['noise_level'] for r in rows})}.",
        "",
    ]

    if hash_embeddings:
        parts += [
            "> **Nicht verwertbar.** Diese Messreihe lief mit Ersatz-Embeddings "
            "(Hash) statt mit Ollama. Sie belegt, dass die Messkette funktioniert, "
            "und sagt nichts ueber die Leistung des Systems. Fuer die Arbeit ist "
            "der Lauf mit Ollama zu wiederholen.",
            "",
        ]
    elif backends:
        parts += [
            f"> Embeddings: {', '.join(sorted(backends))}, lokal berechnet.",
            "",
        ]
    if no_generation:
        parts += [
            "> **Nur Abruf gemessen.** Es lief keine Antwortgenerierung, daher "
            "enthaelt dieser Bericht keine Aussage zur Faktentreue der Antworten - "
            "nur dazu, ob die richtige Textstelle gefunden wurde.",
            "",
        ]
    if cases < 25:
        parts += [
            f"> **Zu wenige Testfaelle.** {cases} statt der geplanten 25 bis 30. "
            "Einzelne Faelle schlagen dadurch stark auf die Quote durch.",
            "",
        ]

    try:
        from answer_scoring import score_results, summarise
        verdicts = summarise(score_results(rows))
        if set(verdicts) - {"not_generated"}:
            labels = {
                "correct": "sachlich richtig",
                "wrong_value": "falscher Wert genannt",
                "no_value": "keine Zahl in der Antwort",
                "refused": "Auskunft verweigert",
                "no_answer": "keine Antwort erzeugt",
                "likely_correct": "vermutlich richtig, zu pruefen",
                "needs_review": "manuell zu pruefen",
            }
            parts += ["## Faktentreue der Antworten", "",
                      "| Bewertung | Anzahl |", "|---|---:|"]
            for verdict, count in sorted(verdicts.items(), key=lambda kv: -kv[1]):
                parts.append(f"| {labels.get(verdict, verdict)} | {count} |")
            parts += ["", "Die Bewertung vergleicht die Zahlen der Antwort mit der "
                          "bekannten richtigen Antwort und schlaegt ein Urteil vor. "
                          "Faelle ohne Zahlenanker sind zur Durchsicht markiert.", ""]
    except Exception as exc:
        print(f"  Faktentreue uebersprungen: {exc}")

    parts += [
        "## Trefferquote nach Dokumentenmenge", "",
        table_hit_rate(rows), "",
        "Die Trefferquote misst, ob der erwartete Chunk unter den abgerufenen war. "
        "Sie ist die diagnostische Zwischenstufe, die RAG gegenueber einem "
        "geschlossenen Sprachmodell auszeichnet: Faellt die Antwortqualitaet, "
        "laesst sich hier ablesen, ob bereits der Abruf versagt hat.", "",
        "## Fehlerarten", "",
        table_errors(rows), "",
        "Der Fehlgriff auf eine verwechselbare Quelle ist der praktisch heikle Fall. "
        "Das System liefert dabei keine erkennbare Luecke, sondern eine plausible "
        "Zahl aus einer ueberholten Preisliste.", "",
        "## Suchzeit", "",
        table_latency(rows), "",
        "Die Suchzeit waechst linear mit dem Korpus, weil die Kosinus-Aehnlichkeit "
        "gegen jeden gespeicherten Chunk berechnet wird.", "",
    ]

    try:
        from plots import write_figures
        figures = write_figures(rows)
        parts += ["## Abbildungen", ""]
        parts += [f"- `{f}`" for f in figures]
        parts += ["", "SVG laesst sich in Word einfuegen und bleibt beim "
                      "Skalieren scharf.", ""]
    except Exception as exc:
        print(f"  Abbildungen uebersprungen: {exc}")
        figures = []

    REPORT.parent.mkdir(exist_ok=True)
    REPORT.write_text("\n".join(parts), encoding="utf-8")
    for figure in figures:
        print(f"Abbildung geschrieben: {figure}")
    print(f"Bericht geschrieben: {REPORT}")
    print("\n" + "\n".join(parts[:1] + parts[4:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
