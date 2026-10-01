#!/usr/bin/env python3
"""
Turn the measurement grid into the tables and figures for Kapitel 4.3.

Reads measurements/results_grid.csv, writes measurements/report_grid.md plus
one figure per noise design.
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from plots import line_chart

GRID = Path("measurements/results_grid.csv")
REPORT = Path("measurements/report_grid.md")
FIGDIR = Path("measurements/figures")

K_VALUES = ["3", "5", "10", "20"]
LEVELS = ["10", "50", "100", "200"]
MODES = ["unrelated", "confusable"]
KATEGORIEN = ["verwechselbar", "kontrolle", "einzelquelle", "qualitativ"]


def load() -> List[Dict]:
    with open(GRID, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rate(rows: List[Dict], field: str = "retrieval_hit") -> float:
    return sum(1 for r in rows if r[field] == "True") / len(rows) if rows else 0.0


def spread(rows: List[Dict], field: str = "retrieval_hit") -> float:
    per = defaultdict(list)
    for r in rows:
        per[r["run"]].append(r[field] == "True")
    vals = [sum(v) / len(v) for v in per.values() if v]
    return statistics.stdev(vals) if len(vals) > 1 else 0.0


def table(rows, mode, kategorie=None, field="retrieval_hit"):
    out = ["| k | " + " | ".join(f"{l} Dok." for l in LEVELS) + " |",
           "|---:|" + "---:|" * len(LEVELS)]
    for k in K_VALUES:
        cells = []
        for lvl in LEVELS:
            s = [r for r in rows
                 if r["k"] == k and r["noise_level"] == lvl
                 and r["noise_mode"] == mode and r["unanswerable"] != "True"
                 and (kategorie is None or r["kategorie"] == kategorie)]
            if not s:
                cells.append("-")
            else:
                sd = spread(s, field)
                cells.append(f"{rate(s, field):.1%}" + (f" ± {sd:.1%}" if sd else ""))
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def precision_table(rows, mode):
    out = ["| k | " + " | ".join(f"{l} Dok." for l in LEVELS) + " |",
           "|---:|" + "---:|" * len(LEVELS)]
    for k in K_VALUES:
        cells = []
        for lvl in LEVELS:
            s = [r for r in rows if r["k"] == k and r["noise_level"] == lvl
                 and r["noise_mode"] == mode and r["unanswerable"] != "True"]
            cells.append(f"{sum(float(r['retrieval_precision']) for r in s)/len(s):.3f}"
                         if s else "-")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def region_table(rows):
    out = ["| Rauschen | k | Tabelle | gemischt | Fliesstext |",
           "|---|---:|---:|---:|---:|"]
    for mode in MODES:
        for k in K_VALUES:
            errs = [r for r in rows if r["noise_mode"] == mode and r["k"] == k
                    and r["unanswerable"] != "True" and r["retrieval_hit"] != "True"]
            if not errs:
                continue
            total = len(errs)
            cells = [f"{sum(1 for r in errs if r['top_region'] == x)/total:.0%}"
                     for x in ("tabelle", "gemischt", "fliesstext")]
            out.append(f"| {mode} | {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def figures(rows) -> List[str]:
    FIGDIR.mkdir(parents=True, exist_ok=True)
    written = []
    for mode in MODES:
        series = []
        for k in K_VALUES:
            vals = []
            for lvl in LEVELS:
                s = [r for r in rows if r["k"] == k and r["noise_level"] == lvl
                     and r["noise_mode"] == mode and r["unanswerable"] != "True"]
                vals.append(rate(s))
            series.append((f"k={k}", vals))
        path = FIGDIR / f"abb_gitter_{mode}.svg"
        path.write_text(
            line_chart(f"Trefferquote nach Korpusgroesse ({mode})",
                       LEVELS, series, "Trefferquote", y_max=1.0, percent=True),
            encoding="utf-8")
        written.append(str(path))
    return written


def main() -> int:
    rows = load()
    ans = [r for r in rows if r["unanswerable"] != "True"]
    unb = [r for r in rows if r["unanswerable"] == "True"]
    kopf = sum(1 for r in ans
               if r["retrieved_chunk_ids"].split("|")[0].endswith("_chunk_0")) / len(ans)

    p = [
        "# Messgitter — Ergebnisse",
        "",
        f"{len(rows)} Messungen: {len({r['case_id'] for r in rows})} Testfaelle "
        f"x {len(LEVELS)} Korpusgroessen x {len(K_VALUES)} k-Werte x 3 Laeufe "
        f"x {len(MODES)} Rauschdesigns. Embeddings: "
        f"{', '.join(sorted({r['embedding_backend'] for r in rows}))}, lokal.",
        "",
        "> **Vorbehalt, der alle folgenden Zahlen betrifft.** Bei "
        f"{kopf:.0%} der Abrufe ist der beste Treffer ein Briefkopf-Chunk "
        "(Firmenname, Adresse, Datum). Die Testfragen nennen die Firma, damit "
        "sie eindeutig sind; ein Briefkopf besteht fast nur aus Firmenname und "
        "Adresse und wird dadurch bevorzugt. Die Trefferquoten messen deshalb "
        "zu einem erheblichen Teil diesen Effekt und nicht die Wirkung des "
        "Rauschens.",
        "",
        "> Es lief keine Antwortgenerierung. Aussagen zur Faktentreue sind aus "
        "diesen Daten nicht ableitbar.",
        "",
        "## Kontrollquote",
        "",
        "Kontrollfaelle fragen nach Angaben, die im Archiv konstant sind "
        "(Stundenansaetze, Erfassung pro Mitarbeiter). Sie muessen immer "
        "gefunden werden; andernfalls ist die Messkette selbst fraglich.",
        "",
        "Chunk-genau — der erwartete Chunk war unter den abgerufenen:",
        "",
        table(rows, "confusable", "kontrolle"),
        "",
        "Inhaltlich — die erwartete Angabe stand irgendwo im Ergebnis:",
        "",
        table(rows, "confusable", "kontrolle", field="content_hit"),
        "",
        "Der Abstand zwischen beiden Tabellen ist selbst ein Befund: Die "
        "Angabe wird gefunden, aber aus einem anderen Dokument. Bei einem Wert, "
        "der in 13 von 14 Offerten identisch steht, misst das chunk-genaue "
        "Kriterium kein Auffinden, sondern willkuerliche Reihenfolge.",
        "",
    ]

    for mode in MODES:
        p += [f"## Trefferquote — Rauschen: {mode}", "", table(rows, mode), "",
              f"### Praezision — {mode}", "", precision_table(rows, mode), ""]

    p += ["## Trefferquote je Analysekategorie (verwechselbares Rauschen)", ""]
    for kat in KATEGORIEN:
        n = len({r["case_id"] for r in rows if r["kategorie"] == kat})
        p += [f"**{kat}** ({n} Faelle)", "", table(rows, "confusable", kat), ""]

    unter = [r for r in rows if r["kategorie"] == "unterspezifiziert"]
    p += ["**unterspezifiziert** "
          f"({len({r['case_id'] for r in unter})} Faelle) — getrennt ausgewiesen "
          "und nicht in den obigen Quoten enthalten, weil die Frage kein "
          "einzelnes Dokument bestimmt.", "",
          table(rows, "confusable", "unterspezifiziert"), ""]

    hal = sum(1 for r in unb if r["error_type"] == "material_fuer_halluzination")
    p += ["## Unbeantwortbare Fragen", "",
          f"{len(unb)} Messungen. In {hal} Faellen ({hal/len(unb):.0%}) lieferte "
          "der Abruf trotzdem Passagen ueber der Schwelle von 0.60. Ohne "
          "Mindestaehnlichkeit bekommt eine nachgeschaltete Generierung also "
          "immer Material, aus dem sich eine selbstsichere Falschantwort bauen "
          "laesst.", "",
          "## Fehler nach Textbereich", "",
          "Anteil der Fehlgriffe, deren bester Treffer aus einem Tabellen-, "
          "einem gemischten oder einem Fliesstextbereich stammt. Ein Chunk gilt "
          "als Tabelle ab 60 Prozent Zeilen mit Betrag, als Fliesstext unter 25 "
          "Prozent, dazwischen als gemischt.", "",
          region_table(rows), ""]

    figs = figures(rows)
    p += ["## Abbildungen", ""] + [f"- `{f}`" for f in figs] + [""]

    REPORT.write_text("\n".join(p), encoding="utf-8")
    print(f"Bericht: {REPORT}")
    for f in figs:
        print(f"Abbildung: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
