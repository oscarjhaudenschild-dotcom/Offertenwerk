# Messergebnisse RAG-Prototyp

Grundlage: 1176 Messungen, 49 Testfaelle (davon 5 unbeantwortbar), 3 Laeufe je Stufe, Rauschstufen [10, 50, 100, 200].

> Embeddings: ollama, lokal berechnet.

> **Nur Abruf gemessen.** Es lief keine Antwortgenerierung, daher enthaelt dieser Bericht keine Aussage zur Faktentreue der Antworten - nur dazu, ob die richtige Textstelle gefunden wurde.

## Trefferquote nach Dokumentenmenge

| Dokumente | confusable (Mittel ± Streuung) | unrelated (Mittel ± Streuung) |
|---:|---:|---:|
| 10 | 24.2% ± 1.3% | 24.2% ± 1.3% |
| 50 | 18.9% ± 3.5% | 20.5% ± 0.0% |
| 100 | 12.9% ± 1.3% | 20.5% ± 0.0% |
| 200 | 9.1% ± 0.0% | 20.5% ± 0.0% |

Die Trefferquote misst, ob der erwartete Chunk unter den abgerufenen war. Sie ist die diagnostische Zwischenstufe, die RAG gegenueber einem geschlossenen Sprachmodell auszeichnet: Faellt die Antwortqualitaet, laesst sich hier ablesen, ob bereits der Abruf versagt hat.

## Fehlerarten

| Fehlerart | confusable | unrelated |
|---|---:|---:|
| richtiges Dokument, falsche Stelle | 206 | 300 |
| falsches Dokument | 4 | 96 |
| Fehlgriff auf verwechselbare Quelle | 232 | 0 |
| Fehlgriff auf unverwandte Quelle | 0 | 19 |
| unbeantwortbar, trotzdem Material geliefert | 60 | 60 |
| richtig | 86 | 113 |

Der Fehlgriff auf eine verwechselbare Quelle ist der praktisch heikle Fall. Das System liefert dabei keine erkennbare Luecke, sondern eine plausible Zahl aus einer ueberholten Preisliste.

## Suchzeit

| Dokumente | Chunks | Suchzeit (ms) |
|---:|---:|---:|
| 10 | 59 | 3.8 |
| 50 | 152 | 7.7 |
| 100 | 271 | 14.0 |
| 200 | 498 | 28.9 |

Die Suchzeit waechst linear mit dem Korpus, weil die Kosinus-Aehnlichkeit gegen jeden gespeicherten Chunk berechnet wird.

## Abbildungen

- `measurements/figures/abb_trefferquote.svg`
- `measurements/figures/abb_suchzeit.svg`

SVG laesst sich in Word einfuegen und bleibt beim Skalieren scharf.
