# Offertenwerk

Dieses Repository dokumentiert den praktischen Teil einer Maturaarbeit zu Retrieval-Augmented Generation: ein Formular-Werkzeug zur Offertenerstellung für ein Treuhandbüro, und den vollständigen Messaufbau, mit dem die Retrieval-Qualität desselben Systems untersucht wird. Beide Teile teilen sich denselben Retrieval-Code (`rag-system/retrieval_core.py`) — das Werkzeug, das in der Praxis benutzt wird, ist dasselbe, das im Messteil gemessen wird.

## Aufbau

- **`app.html`** — das Praxiswerkzeug. Läuft offline im Browser, keine Installation nötig.
- **`rag-system/`** — Korpus, Retrieval-Kern, Ablenker-Generator, Gold-Set und der gesamte Messaufbau.
- **`rag-system/corpus/`** — 14 anonymisierte, historische Offerten als Wissensbasis.
- **`rag-system/measurements/`** — Rohdaten, Berichte und Abbildungen der Messläufe.

Die unanonymisierten Originaldokumente und die Anonymisierungs-Rückübersetzungstabelle sind aus diesem Repository ausgeschlossen (siehe `.gitignore`).

## Ausführen

```bash
cd rag-system
pip install -r requirements.txt
python3 rag.py check                 # prueft Ollama, Embedding-Modell, Korpus
python3 rag.py ask "Wie hoch ist der Ansatz fuer einen Treuhandexperten?"
```

Benötigt [Ollama](https://ollama.com) mit dem Modell `nomic-embed-text`, lokal installiert. Ohne Ollama läuft das System mit einem schwächeren Ersatzverfahren weiter.

## Praxiswerkzeug starten

```bash
cd rag-system
python3 server.py            # startet die lokale Retrieval-Seitenleiste
open ../app.html              # separat, im Browser
```

Ohne laufenden Server funktioniert `app.html` weiterhin vollständig — nur die Seitenleiste „Ähnliche Stellen" bleibt dann ausgeblendet.

## Messung reproduzieren

```bash
cd rag-system
python3 run_grid.py                     # 4 Korpusgroessen x 4 k-Werte x 2 Rauschmodi
python3 build_grid_report.py            # Tabellen und Abbildungen aus den Rohdaten
python3 run_grid.py --strip-letterhead  # Vergleichslauf ohne Briefkopf-Chunks
python3 build_letterhead_report.py
```

Für einen Generierungslauf zusätzlich einen Anthropic-API-Schlüssel setzen:

```bash
export ANTHROPIC_API_KEY="dein-schluessel"
```

## Hinweis zu den Messdaten

Die Messdaten in `measurements/` stammen von einer Wiederholung der Messreihe am 1. Oktober 2026 mit dem neu anonymisierten Korpus. Die Zahlen in der Maturaarbeit (Tabelle 9) stammen aus dem Lauf vom 9. September 2026 mit der ersten Anonymisierung und weichen deshalb um wenige Prozentpunkte ab; die Befunde sind in beiden Läufen gleich.

## Über dieses Projekt

Entstanden als Maturaarbeit, Schwerpunkt Wirtschaft und Recht. Der Retrieval-Teil ist von Grund auf implementiert (Kosinus-Ähnlichkeit von Hand, keine Vektordatenbank), damit die Messkette nachvollziehbar bleibt.
