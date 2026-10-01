#!/usr/bin/env python3
"""
Compare the measurement grid with and without the letterhead stripped.

Reads measurements/results_grid.csv (baseline) and
measurements/results_grid_no_letterhead.csv (comparison), writes
measurements/report_letterhead.md.
"""

import csv
from pathlib import Path
from typing import Dict, List

BEFORE = Path("measurements/results_grid.csv")
AFTER = Path("measurements/results_grid_no_letterhead.csv")
REPORT = Path("measurements/report_letterhead.md")

K_VALUES = ["3", "5", "10", "20"]
LEVELS = ["10", "50", "100", "200"]
MODES = ["confusable", "unrelated"]


def load(path: Path) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def hit_rate(rows: List[Dict], mode: str, k: str, level: str) -> float:
    s = [r for r in rows if r["noise_mode"] == mode and r["k"] == k
         and r["noise_level"] == level and r["unanswerable"] != "True"]
    return sum(1 for r in s if r["retrieval_hit"] == "True") / len(s) if s else 0.0


def hitrate_table(before, after, mode) -> str:
    out = ["| k | " + " | ".join(f"{l} Dok. vorher→nachher" for l in LEVELS) + " |",
           "|---:|" + "---:|" * len(LEVELS)]
    for k in K_VALUES:
        cells = []
        for lvl in LEVELS:
            b = hit_rate(before, mode, k, lvl)
            a = hit_rate(after, mode, k, lvl)
            arrow = "↑" if a > b else ("↓" if a < b else "=")
            cells.append(f"{b:.1%} → {a:.1%} {arrow}")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def error_shares(rows: List[Dict], mode: str) -> Dict:
    s = [r for r in rows if r["noise_mode"] == mode and r["unanswerable"] != "True"]
    n = len(s)
    misses = [r for r in s if r["retrieval_hit"] != "True"]
    return {
        "falsches_dokument": sum(1 for r in s if r["error_type"] == "falsches_dokument") / n,
        "falsche_stelle": sum(1 for r in s if r["error_type"] == "falsche_stelle") / n,
        "fehlgriff_confusable": sum(1 for r in s if r["error_type"] == "fehlgriff_confusable") / n,
        "tabellenfehler_anteil_an_fehlgriffen": (
            sum(1 for r in misses if r["top_region"] == "tabelle") / len(misses)
            if misses else 0.0
        ),
    }


def error_table(before, after) -> str:
    out = ["| Rauschen | Lauf | falsches Dokument | falsche Stelle | Ablenker-Fehlgriff | Tabellenfehler* |",
           "|---|---|---:|---:|---:|---:|"]
    for mode in MODES:
        for label, rows in [("vorher", before), ("nachher", after)]:
            e = error_shares(rows, mode)
            out.append(
                f"| {mode} | {label} | {e['falsches_dokument']:.1%} | "
                f"{e['falsche_stelle']:.1%} | {e['fehlgriff_confusable']:.1%} | "
                f"{e['tabellenfehler_anteil_an_fehlgriffen']:.1%} |"
            )
    return "\n".join(out)


def kontrolle_table(before, after) -> str:
    def rate(rows, k, lvl):
        s = [r for r in rows if r["kategorie"] == "kontrolle" and r["k"] == k
             and r["noise_level"] == lvl and r["noise_mode"] == "confusable"]
        return sum(1 for r in s if r["content_hit"] == "True") / len(s) if s else 0.0

    out = ["| k | " + " | ".join(f"{l} Dok. vorher→nachher" for l in LEVELS) + " |",
           "|---:|" + "---:|" * len(LEVELS)]
    for k in K_VALUES:
        cells = []
        for lvl in LEVELS:
            b, a = rate(before, k, lvl), rate(after, k, lvl)
            cells.append(f"{b:.1%} → {a:.1%}")
        out.append(f"| {k} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def briefkopf_share(rows: List[Dict]) -> float:
    ans = [r for r in rows if r["unanswerable"] != "True"]
    return sum(1 for r in ans
               if r["retrieved_chunk_ids"].split("|")[0].endswith("_chunk_0")) / len(ans)


def main() -> int:
    before, after = load(BEFORE), load(AFTER)

    p = [
        "# Briefkopf-Vergleichslauf",
        "",
        "Zwei vollstaendige Messgitter, identisch bis auf eine Aenderung: In der "
        "zweiten Messung wird vor dem Zerlegen in Chunks der Name-Adresse-Anrede-"
        "Block am Dokumentanfang entfernt (`chunking.strip_letterhead`). Der "
        "Ablenker-Generator ist davon nicht betroffen - er entfernt diesen Block "
        "ohnehin schon beim Erzeugen des Rauschens. Das Formular-Werkzeug "
        "(`app.html`) setzt dieses Flag nie; die Aenderung betrifft ausschliesslich "
        "diese beiden Messlaeufe.",
        "",
        "Weil das Entfernen der Anrede die Wortzahl am Dokumentanfang verschiebt, "
        "wurde der Gold-Standard fuer den zweiten Lauf neu erzeugt "
        "(`gold_set_no_letterhead.json`) statt den alten wiederzuverwenden: 3 von "
        "55 Faellen (LOHN_02, GRUE_02, SONST_01) landen nach dem Entfernen in einem "
        "anderen Chunk als vorher, weil sich die Chunk-Grenze verschiebt. Ohne "
        "eigenen Gold-Standard haetten diese drei Faelle im Vergleichslauf falsch "
        "gezaehlt.",
        "",
        "## Was der Briefkopf-Effekt ist",
        "",
        f"Vorher landete bei **{briefkopf_share(before):.0%}** aller Abrufe der "
        f"Adress-Chunk (chunk_0: Firmenname, Adresse, Datum, Anrede) auf Platz 1 - "
        f"nach dem Entfernen sind es noch **{briefkopf_share(after):.0%}**. Der "
        "Rest davon ist kein Fehler: 12 der 55 Testfragen erwarten die Antwort "
        "tatsaechlich in diesem Chunk (Gruendungsanlass, Ausschluesse und Ähnliches "
        "stehen im Fliesstext direkt nach der Anrede).",
        "",
        "Der Mechanismus: Jede Offerte beginnt mit dem Namen der Klientin in der "
        "Adresse. Die Testfragen nennen diesen Namen ebenfalls, damit sie eindeutig "
        "sind. Dadurch stimmt die Anfrage lexikalisch und semantisch stark mit dem "
        "Adress-Chunk ueberein - unabhaengig davon, wonach die Frage eigentlich "
        "fragt. Bei einer Preisfrage zog das den Adress-Chunk vor die Preistabelle "
        "im selben Dokument, was sich als `falsche_stelle` niederschlug.",
        "",
        "## Die Kehrseite, die erst der Vergleich zeigt",
        "",
        "Der Briefkopf war nicht nur ein Fehler. Er trug zugleich einen echten "
        "Klientennamen, den keine Ablenker-Kopie besitzt - der Ablenker-Generator "
        "vergibt bewusst andere Firmennamen (`Helvetia Textil GmbH` statt `Muster "
        "A GmbH`). Solange der Briefkopf indexiert war, ankerte dieser Namensabgleich "
        "die Suche auf das richtige Dokument, selbst wenn eine Ablenker-Kopie "
        "aehnliche Preise enthielt. Ohne Briefkopf verliert das Retrieval diesen "
        "Anker: Der Anteil `fehlgriff_confusable` (eine Ablenker-Kopie statt des "
        "Originals) steigt im verwechselbaren Modus von 22.5 % auf 65.2 %, und bei "
        "grossem Rauschen und kleinem k faellt die Trefferquote spuerbar - z. B. "
        "bei k=3 und 200 Dokumenten von 20.0 % auf 3.6 %.",
        "",
        "Im Modus mit thematisch fremdem Rauschen (`unrelated`) gibt es diese "
        "Kehrseite nicht: Datenschutz- oder Handelsregistertexte konkurrieren nie "
        "ernsthaft mit einer Preistabelle, mit oder ohne Briefkopf. Dort verbessert "
        "sich die Trefferquote in praktisch jeder Zelle.",
        "",
        "**Lesart fuer die Arbeit:** Die 70-Prozent-Zahl war kein reiner Messfehler, "
        "sie war zweigeteilt. Ein Teil davon versteckte ein echtes Chunking-Problem "
        "(`falsche_stelle`, 41.9 % → 5.6 %). Ein anderer Teil kaschierte, wie wenig "
        "das Embedding selbst zwischen einer echten und einer nachgebauten "
        "Preistabelle unterscheiden kann, sobald der Klientenname als Krücke "
        "wegfaellt. Das zweite ist der staerkere Befund fuer die Diskussion: Es "
        "zeigt, dass die beobachtete Robustheit gegen Preistabellen-Rauschen im "
        "Ausgangslauf teilweise ein Artefakt der Dokumentstruktur war, nicht allein "
        "der Bedeutungsaehnlichkeit.",
        "",
        "## Trefferquote — verwechselbares Rauschen (confusable)",
        "",
        hitrate_table(before, after, "confusable"),
        "",
        "## Trefferquote — themenfremdes Rauschen (unrelated)",
        "",
        hitrate_table(before, after, "unrelated"),
        "",
        "## Fehleranteile (Anteil an allen Messungen je Modus)",
        "",
        error_table(before, after),
        "",
        "\\* Tabellenfehler: Anteil unter den Fehlgriffen (nicht allen Messungen), "
        "deren bester Treffer aus einem Tabellenbereich (>=60% Zeilen mit Betrag) "
        "stammt.",
        "",
        "## Kontrollquote (inhaltlich, verwechselbares Rauschen)",
        "",
        kontrolle_table(before, after),
        "",
        "Vier der sechs Kontrollfaelle liegen ausserhalb des Briefkopfs und "
        "aendern sich kaum. Die Verschlechterung bei kleinem k / grossem Rauschen "
        "betrifft auch sie - derselbe Ankerverlust wie oben, nicht ein neuer "
        "Fehler.",
        "",
    ]

    REPORT.write_text("\n".join(p), encoding="utf-8")
    print(f"Bericht: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
