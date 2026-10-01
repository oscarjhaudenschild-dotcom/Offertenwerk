# Messgitter — Ergebnisse

5760 Messungen: 60 Testfaelle x 4 Korpusgroessen x 4 k-Werte x 3 Laeufe x 2 Rauschdesigns. Embeddings: ollama, lokal.

> **Vorbehalt, der alle folgenden Zahlen betrifft.** Bei 52% der Abrufe ist der beste Treffer ein Briefkopf-Chunk (Firmenname, Adresse, Datum). Die Testfragen nennen die Firma, damit sie eindeutig sind; ein Briefkopf besteht fast nur aus Firmenname und Adresse und wird dadurch bevorzugt. Die Trefferquoten messen deshalb zu einem erheblichen Teil diesen Effekt und nicht die Wirkung des Rauschens.

> Es lief keine Antwortgenerierung. Aussagen zur Faktentreue sind aus diesen Daten nicht ableitbar.

## Kontrollquote

Kontrollfaelle fragen nach Angaben, die im Archiv konstant sind (Stundenansaetze, Erfassung pro Mitarbeiter). Sie muessen immer gefunden werden; andernfalls ist die Messkette selbst fraglich.

Chunk-genau — der erwartete Chunk war unter den abgerufenen:

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 33.3% | 33.3% | 33.3% | 33.3% |
| 5 | 33.3% | 33.3% | 33.3% | 33.3% |
| 10 | 33.3% | 33.3% | 33.3% | 33.3% |
| 20 | 66.7% | 38.9% ± 9.6% | 33.3% | 33.3% |

Inhaltlich — die erwartete Angabe stand irgendwo im Ergebnis:

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 77.8% ± 9.6% | 66.7% | 66.7% | 66.7% |
| 5 | 83.3% | 66.7% | 66.7% | 66.7% |
| 10 | 100.0% | 94.4% ± 9.6% | 66.7% | 66.7% |
| 20 | 100.0% | 100.0% | 88.9% ± 9.6% | 83.3% |

Der Abstand zwischen beiden Tabellen ist selbst ein Befund: Die Angabe wird gefunden, aber aus einem anderen Dokument. Bei einem Wert, der in 13 von 14 Offerten identisch steht, misst das chunk-genaue Kriterium kein Auffinden, sondern willkuerliche Reihenfolge.

## Trefferquote — Rauschen: unrelated

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 39.4% ± 1.0% | 36.4% | 36.4% | 34.5% |
| 5 | 45.5% | 42.4% ± 1.0% | 41.8% | 41.8% |
| 10 | 64.8% ± 1.0% | 62.4% ± 1.0% | 61.2% ± 1.0% | 60.0% |
| 20 | 98.2% | 95.2% ± 1.0% | 94.5% | 90.9% |

### Praezision — unrelated

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 0.131 | 0.121 | 0.121 | 0.115 |
| 5 | 0.091 | 0.085 | 0.084 | 0.084 |
| 10 | 0.065 | 0.062 | 0.061 | 0.060 |
| 20 | 0.049 | 0.048 | 0.047 | 0.045 |

## Trefferquote — Rauschen: confusable

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 36.4% | 28.5% ± 1.0% | 24.8% ± 1.0% | 21.8% |
| 5 | 38.2% | 31.5% ± 1.0% | 28.5% ± 1.0% | 25.5% |
| 10 | 57.0% ± 2.1% | 38.2% | 32.1% ± 1.0% | 29.1% |
| 20 | 86.7% ± 1.0% | 55.8% ± 4.6% | 40.0% ± 3.1% | 32.7% |

### Praezision — confusable

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 0.121 | 0.095 | 0.083 | 0.073 |
| 5 | 0.076 | 0.063 | 0.057 | 0.051 |
| 10 | 0.057 | 0.038 | 0.032 | 0.029 |
| 20 | 0.043 | 0.028 | 0.020 | 0.016 |

## Trefferquote je Analysekategorie (verwechselbares Rauschen)

**verwechselbar** (26 Faelle)

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 9.0% ± 2.2% | 3.8% | 3.8% | 3.8% |
| 5 | 12.8% ± 2.2% | 3.8% | 3.8% | 3.8% |
| 10 | 35.9% ± 5.9% | 11.5% | 6.4% ± 2.2% | 3.8% |
| 20 | 79.5% ± 2.2% | 39.7% ± 8.0% | 17.9% ± 5.9% | 7.7% |

**kontrolle** (6 Faelle)

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 33.3% | 33.3% | 33.3% | 33.3% |
| 5 | 33.3% | 33.3% | 33.3% | 33.3% |
| 10 | 33.3% | 33.3% | 33.3% | 33.3% |
| 20 | 66.7% | 38.9% ± 9.6% | 33.3% | 33.3% |

**einzelquelle** (12 Faelle)

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 47.2% ± 4.8% | 33.3% | 33.3% | 33.3% |
| 5 | 47.2% ± 4.8% | 36.1% ± 4.8% | 33.3% | 33.3% |
| 10 | 75.0% ± 8.3% | 50.0% | 33.3% | 33.3% |
| 20 | 100.0% | 66.7% | 44.4% ± 4.8% | 33.3% |

**qualitativ** (6 Faelle)

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 100.0% | 83.3% | 66.7% | 66.7% |
| 5 | 100.0% | 100.0% | 88.9% ± 9.6% | 66.7% |
| 10 | 100.0% | 100.0% | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% | 100.0% | 100.0% |

**unterspezifiziert** (5 Faelle) — getrennt ausgewiesen und nicht in den obigen Quoten enthalten, weil die Frage kein einzelnes Dokument bestimmt.

| k | 10 Dok. | 50 Dok. | 100 Dok. | 200 Dok. |
|---:|---:|---:|---:|---:|
| 3 | 80.0% | 73.3% ± 11.5% | 53.3% ± 11.5% | 20.0% |
| 5 | 80.0% | 80.0% | 66.7% ± 11.5% | 60.0% |
| 10 | 100.0% | 80.0% | 80.0% | 60.0% |
| 20 | 100.0% | 80.0% | 80.0% | 80.0% |

## Unbeantwortbare Fragen

480 Messungen. In 416 Faellen (87%) lieferte der Abruf trotzdem Passagen ueber der Schwelle von 0.60. Ohne Mindestaehnlichkeit bekommt eine nachgeschaltete Generierung also immer Material, aus dem sich eine selbstsichere Falschantwort bauen laesst.

## Fehler nach Textbereich

Anteil der Fehlgriffe, deren bester Treffer aus einem Tabellen-, einem gemischten oder einem Fliesstextbereich stammt. Ein Chunk gilt als Tabelle ab 60 Prozent Zeilen mit Betrag, als Fliesstext unter 25 Prozent, dazwischen als gemischt.

| Rauschen | k | Tabelle | gemischt | Fliesstext |
|---|---:|---:|---:|---:|
| unrelated | 3 | 46% | 3% | 51% |
| unrelated | 5 | 41% | 3% | 55% |
| unrelated | 10 | 48% | 0% | 52% |
| unrelated | 20 | 34% | 0% | 66% |
| confusable | 3 | 47% | 9% | 44% |
| confusable | 5 | 49% | 7% | 44% |
| confusable | 10 | 51% | 6% | 43% |
| confusable | 20 | 55% | 7% | 38% |

## Abbildungen

- `measurements/figures/abb_gitter_unrelated.svg`
- `measurements/figures/abb_gitter_confusable.svg`
