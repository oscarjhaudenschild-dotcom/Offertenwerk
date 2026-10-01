# KI-Deklaration

Die Wegleitung Informatik der KSM verlangt, dass KI-generierte Codeanteile
gekennzeichnet werden, damit die Arbeit reproduzierbar bleibt. Dieses Dokument
hält fest, welche Teile wie entstanden sind.

## Zusammenfassung

Der gesamte Code unter `rag-system/` wurde im Dialog mit Claude (Anthropic)
über Claude Code erstellt. Die Vorgaben stammen von Oscar Haudenschild: das
technische Briefing, die Forschungsfrage, die Messgrössen, die Entscheidung für
lokale Embeddings, für eine selbst geschriebene Kosinus-Ähnlichkeit sowie die
Abgrenzung, dass Preise nicht in den Abrufpfad gehören.

Das Formular-Tool `app.html` (Stufe 1) entstand in früheren Sitzungen, ebenfalls
im Dialog mit einem KI-Assistenten.

## Entstehung im Einzelnen

| Datei | Entstehung |
|---|---|
| `chunking.py` | KI-generiert nach Vorgabe (konfigurierbare Chunk-Grösse, Overlap) |
| `embeddings.py` | KI-generiert; Offline-Ersatz auf Anregung der KI ergänzt, da Ollama fehlte |
| `retrieval.py` | KI-generiert nach ausdrücklicher Vorgabe, die Kosinus-Ähnlichkeit von Hand statt per Bibliothek zu schreiben |
| `rag_system.py` | KI-generiert |
| `corpus_builder.py` | KI-generiert; die beiden Rauschvarianten gehen auf einen Befund der KI zurück (siehe unten) |
| `gold_set.py` | Struktur KI-generiert; die inhaltlichen Testfälle stammen fachlich aus den anonymisierten Offerten im Korpus |
| `measurement.py` | KI-generiert |
| `answer_scoring.py` | KI-generiert |
| `plots.py` | KI-generiert |
| `anonymise.py` | KI-generiert |
| `build_report.py`, `analyze_results.py` | KI-generiert |
| `rag.py`, `verify_setup.py` | KI-generiert |
| Testfälle im Gold-Set | fachlich von Oscar, Formulierung KI-unterstützt |

## Vorgaben, die von Oscar stammen

- Forschungsfrage und Messgrössen
- Lokale Embeddings aus Datenschutzgründen (revDSG, Berufsgeheimnis)
- Kosinus-Ähnlichkeit selbst implementieren, damit sie im Fachgespräch erklärbar ist
- Einfache RAG-Grundform statt modularer Variante
- Preise und Stufen fest im Code, nicht in der Wissensbasis
- Kein Vergleich mit Long-Context-Verfahren
- Rauschstufen 10 / 50 / 100 / 200

## Befunde, die aus der KI-Zusammenarbeit hervorgingen

Diese Punkte standen nicht im Briefing und ergaben sich beim Bauen und Testen:

1. **Rauschen muss verwechselbar sein.** Mit thematisch unverwandten
   Rauschdokumenten blieb die Trefferquote über alle Stufen konstant. Erst
   Dokumente, die den Antwortdokumenten gleichen und nur andere Zahlen
   enthalten, erzeugen den messbaren Qualitätsabfall. Das führte zu den zwei
   Rauschvarianten `unrelated` und `confusable`.

2. **Rauschen darf die richtige Antwort nicht enthalten.** Ein erster Ansatz
   erzeugte Rauschen durch Umstellen der Basisdokumente; diese enthielten die
   gesuchten Zahlen weiterhin. Ein Fehlgriff hätte dann zufällig die richtige
   Antwort geliefert und die Trefferquote beschönigt.

3. **Fehlerarten trennen.** Der Abruf einer überholten, aber plausibel
   wirkenden Preisliste ist praktisch gefährlicher als der Abruf eines
   thematisch unpassenden Dokuments. Beide werden getrennt gezählt.

## Fehler, die beim Testen gefunden wurden

Der Code wurde nicht nur geschrieben, sondern ausgeführt. Dabei traten Fehler
auf, die ohne Ausführung unbemerkt geblieben wären:

- Die Messreihe ersetzte den Basiskorpus durch die Rauschdokumente. Die
  Trefferquote wäre durchgehend null gewesen.
- Der Embedding-Cache verwendete die ersten 200 Zeichen als Schlüssel. Da sich
  benachbarte Chunks überlappen, erhielten verschiedene Chunks denselben Vektor.
- Der Cache nutzte Pythons `hash()`, das je Prozess anders ausfällt; er griff
  über Läufe hinweg nie.
- Sätze ohne Satzzeichen wurden nie geteilt; eine Tabelle wäre als ein einziger
  überlanger Chunk in die Suche gegangen.
- Die Anonymisierung ordnete derselben Firma zwei verschiedene Pseudonyme zu,
  wenn ein Artikel davorstand.

## Stand der Prüfung

Ausgeführt und geprüft: Chunking, Kosinus-Ähnlichkeit, Messreihe, CSV-Ausgabe,
Bericht, Abbildungen, Anonymisierung, Antwortbewertung, der Ollama-Pfad und
die PDF-Extraktion.

Die Messwerte in `measurements/` entstanden mit echten lokalen Embeddings
über Ollama, Modell `nomic-embed-text` (Version 1.5), nicht im
Offline-Ersatzmodus. Der Offline-Modus mit Hash-Embeddings existiert
weiterhin im Code (`embedding_backend="hash"`), dient aber nur dazu, die
Pipeline ohne installiertes Ollama zu testen, und ist nicht die Grundlage
der berichteten Zahlen.

---

Letzte Aktualisierung: 2026-09-06
