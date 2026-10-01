# Briefkopf-Vergleichslauf

Zwei vollstaendige Messgitter, identisch bis auf eine Aenderung: In der zweiten Messung wird vor dem Zerlegen in Chunks der Name-Adresse-Anrede-Block am Dokumentanfang entfernt (`chunking.strip_letterhead`). Der Ablenker-Generator ist davon nicht betroffen - er entfernt diesen Block ohnehin schon beim Erzeugen des Rauschens. Das Formular-Werkzeug (`app.html`) setzt dieses Flag nie; die Aenderung betrifft ausschliesslich diese beiden Messlaeufe.

Weil das Entfernen der Anrede die Wortzahl am Dokumentanfang verschiebt, wurde der Gold-Standard fuer den zweiten Lauf neu erzeugt (`gold_set_no_letterhead.json`) statt den alten wiederzuverwenden: 3 von 55 Faellen (LOHN_02, GRUE_02, SONST_01) landen nach dem Entfernen in einem anderen Chunk als vorher, weil sich die Chunk-Grenze verschiebt. Ohne eigenen Gold-Standard haetten diese drei Faelle im Vergleichslauf falsch gezaehlt.

## Was der Briefkopf-Effekt ist

Vorher landete bei **52%** aller Abrufe der Adress-Chunk (chunk_0: Firmenname, Adresse, Datum, Anrede) auf Platz 1 - nach dem Entfernen sind es noch **27%**. Der Rest davon ist kein Fehler: 12 der 55 Testfragen erwarten die Antwort tatsaechlich in diesem Chunk (Gruendungsanlass, Ausschluesse und Ähnliches stehen im Fliesstext direkt nach der Anrede).

Der Mechanismus: Jede Offerte beginnt mit dem Namen der Klientin in der Adresse. Die Testfragen nennen diesen Namen ebenfalls, damit sie eindeutig sind. Dadurch stimmt die Anfrage lexikalisch und semantisch stark mit dem Adress-Chunk ueberein - unabhaengig davon, wonach die Frage eigentlich fragt. Bei einer Preisfrage zog das den Adress-Chunk vor die Preistabelle im selben Dokument, was sich als `falsche_stelle` niederschlug.

## Die Kehrseite, die erst der Vergleich zeigt

Der Briefkopf war nicht nur ein Fehler. Er trug zugleich einen echten Klientennamen, den keine Ablenker-Kopie besitzt - der Ablenker-Generator vergibt bewusst andere Firmennamen (`Helvetia Textil GmbH` statt `Muster A GmbH`). Solange der Briefkopf indexiert war, ankerte dieser Namensabgleich die Suche auf das richtige Dokument, selbst wenn eine Ablenker-Kopie aehnliche Preise enthielt. Ohne Briefkopf verliert das Retrieval diesen Anker: Der Anteil `fehlgriff_confusable` (eine Ablenker-Kopie statt des Originals) steigt im verwechselbaren Modus von 22.5 % auf 65.2 %, und bei grossem Rauschen und kleinem k faellt die Trefferquote spuerbar - z. B. bei k=3 und 200 Dokumenten von 20.0 % auf 3.6 %.

Im Modus mit thematisch fremdem Rauschen (`unrelated`) gibt es diese Kehrseite nicht: Datenschutz- oder Handelsregistertexte konkurrieren nie ernsthaft mit einer Preistabelle, mit oder ohne Briefkopf. Dort verbessert sich die Trefferquote in praktisch jeder Zelle.

**Lesart fuer die Arbeit:** Die 70-Prozent-Zahl war kein reiner Messfehler, sie war zweigeteilt. Ein Teil davon versteckte ein echtes Chunking-Problem (`falsche_stelle`, 41.9 % → 5.6 %). Ein anderer Teil kaschierte, wie wenig das Embedding selbst zwischen einer echten und einer nachgebauten Preistabelle unterscheiden kann, sobald der Klientenname als Krücke wegfaellt. Das zweite ist der staerkere Befund fuer die Diskussion: Es zeigt, dass die beobachtete Robustheit gegen Preistabellen-Rauschen im Ausgangslauf teilweise ein Artefakt der Dokumentstruktur war, nicht allein der Bedeutungsaehnlichkeit.

## Trefferquote — verwechselbares Rauschen (confusable)

| k | 10 Dok. vorher→nachher | 50 Dok. vorher→nachher | 100 Dok. vorher→nachher | 200 Dok. vorher→nachher |
|---:|---:|---:|---:|---:|
| 3 | 36.4% → 32.1% ↓ | 28.5% → 11.5% ↓ | 24.8% → 7.9% ↓ | 21.8% → 3.6% ↓ |
| 5 | 38.2% → 48.5% ↑ | 31.5% → 24.8% ↓ | 28.5% → 12.1% ↓ | 25.5% → 7.3% ↓ |
| 10 | 57.0% → 73.9% ↑ | 38.2% → 41.8% ↑ | 32.1% → 24.2% ↓ | 29.1% → 16.4% ↓ |
| 20 | 86.7% → 97.6% ↑ | 55.8% → 61.8% ↑ | 40.0% → 42.4% ↑ | 32.7% → 27.3% ↓ |

## Trefferquote — themenfremdes Rauschen (unrelated)

| k | 10 Dok. vorher→nachher | 50 Dok. vorher→nachher | 100 Dok. vorher→nachher | 200 Dok. vorher→nachher |
|---:|---:|---:|---:|---:|
| 3 | 39.4% → 46.1% ↑ | 36.4% → 43.6% ↑ | 36.4% → 43.6% ↑ | 34.5% → 41.8% ↑ |
| 5 | 45.5% → 64.8% ↑ | 42.4% → 61.8% ↑ | 41.8% → 60.6% ↑ | 41.8% → 60.0% ↑ |
| 10 | 64.8% → 94.5% ↑ | 62.4% → 90.9% ↑ | 61.2% → 90.3% ↑ | 60.0% → 87.3% ↑ |
| 20 | 98.2% → 100.0% ↑ | 95.2% → 97.6% ↑ | 94.5% → 95.2% ↑ | 90.9% → 92.7% ↑ |

## Fehleranteile (Anteil an allen Messungen je Modus)

| Rauschen | Lauf | falsches Dokument | falsche Stelle | Ablenker-Fehlgriff | Tabellenfehler* |
|---|---|---:|---:|---:|---:|
| confusable | vorher | 0.6% | 33.6% | 27.8% | 50.0% |
| confusable | nachher | 1.0% | 6.2% | 59.5% | 41.5% |
| unrelated | vorher | 7.3% | 31.2% | 0.0% | 44.4% |
| unrelated | nachher | 15.6% | 8.3% | 0.0% | 30.5% |

\* Tabellenfehler: Anteil unter den Fehlgriffen (nicht allen Messungen), deren bester Treffer aus einem Tabellenbereich (>=60% Zeilen mit Betrag) stammt.

## Kontrollquote (inhaltlich, verwechselbares Rauschen)

| k | 10 Dok. vorher→nachher | 50 Dok. vorher→nachher | 100 Dok. vorher→nachher | 200 Dok. vorher→nachher |
|---:|---:|---:|---:|---:|
| 3 | 77.8% → 77.8% | 66.7% → 33.3% | 66.7% → 22.2% | 66.7% → 0.0% |
| 5 | 83.3% → 94.4% | 66.7% → 66.7% | 66.7% → 50.0% | 66.7% → 0.0% |
| 10 | 100.0% → 100.0% | 94.4% → 94.4% | 66.7% → 83.3% | 66.7% → 66.7% |
| 20 | 100.0% → 100.0% | 100.0% → 100.0% | 88.9% → 83.3% | 83.3% → 83.3% |

Vier der sechs Kontrollfaelle liegen ausserhalb des Briefkopfs und aendern sich kaum. Die Verschlechterung bei kleinem k / grossem Rauschen betrifft auch sie - derselbe Ankerverlust wie oben, nicht ein neuer Fehler.
