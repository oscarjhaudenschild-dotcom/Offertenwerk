# Offertenwerk RAG

Messinstrument für die Maturaarbeit: Wie verändert sich die Abrufqualität eines
RAG-Systems, wenn die Wissensbasis mit irrelevanten Dokumenten wächst?

Zweitzweck: ein benutzbares Werkzeug für ein Treuhandbüro.

## Alles, was man braucht

```bash
python3 rag.py check                 # Ist alles installiert?
python3 rag.py ask "deine Frage"     # Wissensbasis befragen
python3 rag.py experiment            # Messreihe laufen lassen
python3 rag.py report                # Tabellen für Kapitel 4.3
python3 rag.py add offerte.pdf       # Dokument aufnehmen
```

Es läuft ohne Installation und ohne Internet. Fehlt Ollama, weicht das System
auf schwächere Embeddings aus und sagt das deutlich — solche Läufe prüfen die
Messkette, liefern aber keine Zahlen für die Arbeit.

## Für belastbare Zahlen

```bash
brew install ollama && ollama serve      # eigenes Terminal
ollama pull nomic-embed-text
pip3 install anthropic                   # nur für formulierte Antworten
export ANTHROPIC_API_KEY="sk-..."
```

`python3 rag.py check` sagt danach, was noch fehlt.

## Wie die Messung funktioniert

Die Wissensbasis besteht aus zwei Teilen. Die **Basisdokumente** enthalten die
gesuchten Antworten und bleiben in jedem Durchgang gleich. Dazu kommen
**Rauschdokumente** in wachsender Zahl — 10, 50, 100, 200.

Das Rauschen gibt es in zwei Ausführungen, und der Unterschied ist der Kern des
Experiments:

- `unrelated` — andere Themen (Archivierung, Handelsregister, Datenschutz).
  Der leichte Fall: solche Dokumente konkurrieren nicht um die Antwort.
- `confusable` — überholte Preislisten. Gleiche Formulierungen wie die
  Basisdokumente, aber durchgehend andere Zahlen, versehen mit Kopfzeilen wie
  „Tarifblatt 2018". Das bildet die reale Gefahr in einem gewachsenen Archiv ab.

Keine Zahl eines Rauschdokuments stimmt je mit einer Zahl seiner Vorlage
überein. Sonst könnte ein Fehlgriff zufällig doch die richtige Antwort liefern
und die Trefferquote beschönigen.

## Was gemessen wird

Pro Testfall und Rauschstufe eine Zeile in der CSV:

| Feld | Bedeutung |
|---|---|
| `retrieval_hit` | War der erwartete Chunk unter den abgerufenen? |
| `error_type` | Art des Fehlgriffs, siehe unten |
| `retrieval_precision` / `_recall` | Genauigkeit und Vollständigkeit des Abrufs |
| `top_similarity` | Ähnlichkeit des besten Treffers |
| `confusable_in_topk` | Wie viele überholte Quellen mitgeliefert wurden |
| `retrieved_chunk_ids` | Vollständige Spur — jeder Abruf ist nachvollziehbar |
| `retrieval_time_ms` | Suchzeit |

Fehlerarten:

- `hit` — erwarteter Chunk gefunden
- `fehlgriff_confusable` — überholte, plausibel wirkende Quelle abgerufen.
  Der gefährliche Fall: das Ergebnis sieht richtig aus.
- `fehlgriff_unrelated` — thematisch unpassende Quelle abgerufen
- `miss_other_source` — verfehlt, ohne dass Rauschen im Ergebnis war
- `no_expectation` — Testfall noch nicht annotiert

## Aufbau

| Datei | Aufgabe |
|---|---|
| `rag.py` | Einstiegspunkt, alle Befehle |
| `chunking.py` | Zerlegung in Chunks |
| `embeddings.py` | Ollama, Cache, Offline-Ersatz |
| `retrieval.py` | Kosinus-Ähnlichkeit, von Hand geschrieben |
| `rag_system.py` | Ablauf Aufnahme → Abruf → Antwort |
| `corpus_builder.py` | Dokumente laden, Rauschen erzeugen |
| `gold_set.py` | Testfälle mit bekannter Antwort |
| `measurement.py` | Messreihe, CSV |
| `build_report.py` | Tabellen für die Arbeit |
| `analyze_results.py` | Auswertung im Terminal |
| `verify_setup.py` | Selbstprüfung |

Die Kosinus-Ähnlichkeit ist bewusst selbst geschrieben statt aus einer
Bibliothek geholt. Sie ist der Kern des Abrufs, und im Fachgespräch muss jeder
Rechenschritt erklärbar sein.

## Testfälle

`measurements/gold_set.json` enthält sechs Beispielfälle, die zeigen, dass die
Messkette trägt. Die Arbeit braucht 25 bis 30 gegen den echten Korpus.

Ein Fall besteht aus Szenario, Frage, bekannter Antwort und den Chunks, die
gefunden werden *müssten* — Letzteres macht die Trefferquote überhaupt messbar.

## Nächste Schritte

1. Ollama installieren, damit echte Embeddings möglich sind
2. Anonymisierte Offerten und Schweizer Rechtsquellen aufnehmen
3. Einmal ohne Rauschen laufen lassen, abgerufene Chunks sichten, `expected_chunk_ids` eintragen
4. Gold-Set auf 25 bis 30 Fälle bringen
5. Messreihe fahren, Bericht erzeugen
