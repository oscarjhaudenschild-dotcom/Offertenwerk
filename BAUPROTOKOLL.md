# Bauprotokoll

Stand: 2026-09-09

Ziel dieses Bauabschnitts: Der Satz im Methodikkapitel — „das Tool wird um eine
RAG-Komponente erweitert" — soll wörtlich zutreffen. Bis hierher waren es zwei
Programme ohne gemeinsamen Code.

---

## Was geändert wurde

### Neu: `rag-system/retrieval_core.py`

Der Abruf liegt jetzt in einem eigenen Modul, das beide Aufrufer benutzen: der
Messaufbau und der Dienst hinter der Offerten-Seitenleiste. Damit ist der
Retrieval-Code, den der Praxispartner benutzt, derselbe, der im Skalierungstest
gemessen wird — nicht eine zweite Umsetzung, die ihm nur ähnelt.

Zwei Ausgänge, absichtlich verschieden:

- `search()` liefert Chunks in der internen Form, unverändert, damit der
  Messaufbau Zeile für Zeile gleich bleibt.
- `find()` liefert eine stabile öffentliche Form (Text, Quelldokument, Score).

Zusätzlich ein Zwischenspeicher über Dateidatum und -grösse, damit ein
laufender Dienst den Korpus nicht bei jeder Anfrage neu einbettet.

**Beleg der Gleichheit:** Messreihe vor und nach dem Umbau, CSV-Vergleich ohne
die Zeitspalten — 24 von 24 Zeilen identisch in beiden Rauschmodi.

### Geändert: `rag-system/rag_system.py`

Benutzt jetzt `RetrievalCore`. `corpus`, `chunker` und `embeddings` bleiben als
Eigenschaften erhalten, weil `measurement.py` direkt darauf zugreift.

Ausserdem: Fehlt der API-Schlüssel, wird die Generierung übersprungen statt
abzustürzen. Vorher brach die ganze Messreihe ab, sobald `anthropic` installiert
war, aber kein Schlüssel gesetzt — und damit ging auch die Abrufmessung
verloren, die gar keinen Schlüssel braucht.

### Neu: `rag-system/server.py`

Lokaler Dienst, nur `127.0.0.1`, eine Route `POST /similar` und `GET /health`.

Nur Standardbibliothek — kein Flask, keine Installation. Das war deine
Entscheidung und sie gilt auch für den Praxispartner.

**Harte Grenze:** Der Dienst importiert keinen Cloud-Client. Embeddings laufen
über Ollama auf dem Gerät. Der Korpus enthält Klientendaten, deshalb ist das
eine Struktureigenschaft und nicht bloss eine Voreinstellung. Kommt später ein
Schritt „Entwurf formulieren" dazu, dann über ein lokales Modell in Ollama.

Der Dienst bricht mit klarer Meldung ab, wenn Ollama fehlt, statt still auf
Ersatz-Embeddings auszuweichen — die würden schlechte Vorschläge liefern, ohne
dass es jemand merkt.

### Geändert: `app.html` (+ ca. 150 Zeilen am Dateiende)

Ein in sich geschlossener Block. Am bestehenden Markup wurde nichts geändert;
die Knöpfe werden beim Laden per JavaScript angehängt.

- Neben jedem der 18 Textfelder ein Knopf „Ähnliche Stellen".
- Treffer erscheinen darunter mit Quelldokument, Textstelle und Einstufung
  hoch/mittel/niedrig.
- „Text übernehmen" hängt die Stelle an das Feld an, von dem aus gefragt wurde.

**Preislogik und Export sind unberührt.** Belegt: Alle Summenzeilen vor und nach
dem Übernehmen identisch.

**Beträge werden beim Übernehmen entfernt.** Beim Prüfen zeigte sich, dass eine
übernommene Textstelle die Honorare des *anderen* Klienten mitbringt — im
Fliesstext, wo sie beim Korrekturlesen kaum auffallen. Übernommener Text
enthält jetzt `CHF ___` statt der Zahl; der Wortlaut bleibt, die Zahl muss
bewusst eingetragen werden. Gemessen: 0 Fremdbeträge.

**Ohne Dienst passiert nichts.** Antwortet `/health` nicht, werden gar keine
Knöpfe angelegt. Geprüft: 0 Knöpfe, 19 Textfelder unverändert, keine Fehler in
der Konsole.

### Geändert: `rag-system/measurement.py`

Neue Fehlerklassen. Vorher fiel alles ausser „Treffer" und Rauschtreffern in
einen Restposten. Auf einem echten Korpus ist gerade dort der interessante
Unterschied:

| Klasse | Bedeutung |
|---|---|
| `richtig` | erwartete Stelle abgerufen |
| `falsche_stelle` | richtiges Dokument, falsche Passage — Chunking-Problem |
| `falsches_dokument` | anderer Klient — Suchproblem |
| `fehlgriff_confusable` | erzeugte verwechselbare Quelle |
| `fehlgriff_unrelated` | erzeugte Fremdquelle |
| `nichts_gefunden` | leeres Ergebnis |
| `material_fuer_halluzination` | unbeantwortbar, trotzdem Passagen ≥ 0.60 |
| `korrekt_abgelehnt` | unbeantwortbar, nichts Überzeugendes gefunden |

Ausserdem: drei Läufe je Rauschstufe mit zufällig gezogener Zusammensetzung
(fester Startwert 20260909, damit der Lauf wiederholbar ist), und neue Spalten
`run`, `expected_document`, `retrieved_documents`, `unanswerable`,
`embedding_backend`.

### Neu: `rag-system/build_gold_set.py`

Erzeugt den Gold Set **aus** dem Korpus. Jeder Fall nennt Frage, Zieldokument
und einen Anker; das Skript sucht die Stelle und liest den Betrag aus dem
Dokument.

Grund: Die Anonymisierung skaliert jede Zahl. Ein von Hand geschriebener
Sollwert liefe beim nächsten Faktorwechsel aus dem Tritt. So kann der Gold Set
den Dokumenten nicht widersprechen.

Ergebnis: 33 Fälle — 28 beantwortbar, 5 unbeantwortbar. Geprüft: bei allen 28
steht die erwartete Antwort tatsächlich im erwarteten Chunk.

### Geändert: `rag-system/anonymise.py`

Drei Fehler, alle beim Prüfen an echten Dokumenten gefunden:

1. **Muster liefen über Zeilenumbrüche.** „Freundliche Grüsse\nMUSTER TREUHAND
   AG" wurde als ein Firmenname gelesen; dieselbe Firma bekam dadurch zwei
   Pseudonyme. Jetzt `[ \t]+` statt `\s+`.
2. **Bereiche wurden halb skaliert.** Bei „CHF 15'000 - 18'000" trägt nur die
   erste Zahl das CHF, also blieb die zweite der echte Wert — ein Leck und ein
   zerstörtes Verhältnis. Jetzt werden beide skaliert.
3. **Jahreszahlen wurden für Postleitzahlen gehalten.** „Zug, 15th January 2025
   CK" wurde zu „0000 Musterort". Die Regel ist jetzt an den Zeilenanfang
   gebunden.

Ausserdem englische Anreden („Dear Richard"), Firmen ohne Rechtsform („Open
Game Foundation"), Strassen, Vor-/Nachname-Verknüpfung, sowie `--keep` und
`--also`. Von 12 durchgerutschten Namen auf 0.

### Geändert: `rag-system/rag.py`

Neuer Befehl `anonymise`. `.docx` wird über `textutil` gelesen (macOS-Bordmittel).
`experiment` nutzt jetzt den echten Korpus und echte Embeddings, sobald
`corpus/` gefüllt ist, und sagt es deutlich, wenn es auf den Demo-Korpus
zurückfällt.

---

## Entscheidungen, die du begründen können musst

| Entscheidung | Wert | Begründung |
|---|---|---|
| Chunk-Grösse | 400 Wörter | Passt zur Absatzlänge der Offerten. **Siehe Befund unten — dieser Wert ist die wahrscheinlichste Ursache der schwachen Trefferquote.** |
| Überlappung | 50 Wörter | Soll Themenwechsel an Chunk-Grenzen abfedern. |
| k | 3 | Genug Kontext für eine Antwort, wenig genug zum Prüfen von Hand. |
| Embedding-Modell | `nomic-embed-text` über Ollama | Lokal, damit Klientendaten das Gerät nicht verlassen. |
| Ähnlichkeitsmass | Kosinus, selbst geschrieben | Muss im Fachgespräch erklärbar sein. Kein FAISS, keine Vektordatenbank — die Suche vergleicht linear gegen jeden Chunk, was die wachsende Suchzeit erklärt. |
| Schwelle hoch/mittel/niedrig | 0.75 / 0.60 | Aus Beobachtung: eine richtige Passage lag bei ~0.80, ein reiner Briefkopf noch bei 0.67. |
| Schwelle „Halluzinationsmaterial" | 0.60 | Ab hier liefert der Abruf einer Generierung genug Stoff für eine selbstsichere Falschantwort. |
| Skalierungsfaktor Beträge | 0.85 | Echte Honorare dürfen nicht in die Arbeit; Verhältnisse bleiben erhalten, weil das Experiment auf ihnen beruht. |
| Rundung | 50er ab CHF 1'000, sonst 10er | Bei durchgehend 50ern fiel „CHF 160-180" auf „CHF 150-150" zusammen. |
| Läufe je Stufe | 3, Startwert 20260909 | Eine einzelne Zusammensetzung kann glücklich sein. |

---

## Was die Messung ergab

Erste Reihe mit echtem Korpus (8 anonymisierte Offerten), echten
Ollama-Embeddings, 33 Fällen, 3 Läufen je Stufe:

| Dokumente | verwechselbar | unverwandt |
|---:|---:|---:|
| 10 | 31.0 % ± 2.1 | 38.1 % ± 2.1 |
| 50 | 19.0 % ± 2.1 | 32.1 % ± 0.0 |
| 100 | 10.7 % ± 3.6 | 32.1 % ± 0.0 |
| 200 | 7.1 % ± 0.0 | 32.1 % ± 0.0 |

Drei Befunde, die im Diskussionsteil hingehören:

**1. Der häufigste Fehler ist nicht das falsche Dokument, sondern die falsche
Stelle darin.** `falsche_stelle` kommt 146- beziehungsweise 192-mal vor,
`falsches_dokument` nur 1- beziehungsweise 12-mal. Die Suche findet also meist
die richtige Offerte und greift darin daneben. Das ist ein Chunking-Problem,
kein Suchproblem — und ohne die Trennung dieser beiden Klassen hättest du das
Gegenteil geschlossen.

**2. Bei allen 5 unbeantwortbaren Fragen lieferte das System trotzdem
Passagen** — 60 von 60 Messungen. Der Abruf gibt immer seine besten drei
zurück, unabhängig davon, wie schlecht sie passen. Ohne Mindestähnlichkeit
bekommt eine Generierung also in jedem Fall Material, aus dem sich eine
selbstsichere Antwort bauen lässt.

**3. Verwechselbares Rauschen bricht den Abruf, unverwandtes nicht.** Die
unverwandte Kurve liegt ab 50 Dokumenten flach bei 32 %; die verwechselbare
fällt auf 7 %. Nicht die Menge schadet, sondern die Ähnlichkeit.

---

## KI-Deklaration

Der gesamte Code dieses Bauabschnitts wurde im Dialog mit Claude (Anthropic)
über Claude Code geschrieben: `retrieval_core.py`, `server.py`,
`build_gold_set.py`, die Änderungen an `measurement.py`, `anonymise.py`,
`rag_system.py`, `build_report.py`, `rag.py` sowie der Seitenleisten-Block in
`app.html`.

Von dir stammen: Zielsetzung, die beiden Architekturentscheide (keine
zusätzliche Abhängigkeit; Knopf je Feld statt automatischer Zuordnung), die
Datenschutzgrenze (kein Cloud-Aufruf im Dienst), die Auflagen zur Preislogik
und zur Lauffähigkeit ohne Server, sowie die Vorgabe der fünf Fehlerklassen.

Die acht Beispieloffere wurden aus dem Chatverlauf transkribiert, nicht aus den
Originaldateien konvertiert. Die Zahlen stimmen mit den von dir gelieferten
Texten überein, aber die Originale sind die massgebliche Quelle.

`KI_DEKLARATION.md` im Ordner `rag-system/` führt den vorherigen Stand.

---

## Was noch nicht funktioniert

**Die Antwortgenerierung ist weiterhin ungeprüft.** Der Code läuft, aber es lief
noch kein einziger Durchgang mit gesetztem Schlüssel. `embedding_backend` und
`generation_skipped` stehen jetzt in der CSV, damit der Bericht das nicht
verschleiert. Schreib nichts über Faktentreue in die Arbeit, bevor das gelaufen
ist.

**Die Trefferquote ist niedrig, und der wahrscheinlichste Grund ist die
Chunk-Grösse.** Bei 400 Wörtern und Offerten von zwei bis drei Chunks trennt
das Chunking Bezeichnung und Preis. Beim Bau des Gold Sets trat genau das auf:
Bei einem Fall stand „Salary administration (fee per employee/year)" in einem
anderen Chunk als „CHF 1'000". Ein Vergleichslauf mit 150 bis 200 Wörtern wäre
ein eigenes, gut begründetes Ergebnis für Kapitel 4 — nicht bloss eine
Verbesserung, sondern die Messung, die den Hauptbefund erklärt.

**Der Fülltext-Generator stammt noch aus der Demo-Zeit.** `corpus_builder.py`
erzeugt das Rauschen aus dem Basiskorpus, was für die echten Offerten
funktioniert, aber Branche und Mitarbeiterzahl nicht eigenständig variiert, wie
du es beschrieben hast.

**Die Seitenleiste ist auf `file://` ungeprüft.** Der volle Durchlauf wurde über
HTTP getestet, weil die Vorschau hier keine echte lokale Datei lädt. Beim
Doppelklick im echten Browser kann die Anfrage an `localhost` an
Sicherheitsregeln scheitern. Das musst du einmal selbst prüfen:

```bash
cd ~/projects/offerten-maker/rag-system && python3 server.py --corpus corpus
```

Dann `app.html` doppelklicken. Erscheinen die Knöpfe, ist alles in Ordnung.

**Nur 8 Dokumente.** Die restlichen 18 Offerten laufen mit einem Befehl durch,
sobald du sie hast.

**Der Praxispartner braucht für die Seitenleiste Python, Ollama und den
laufenden Dienst.** Für den Alltag behält er die eigenständige Datei. Die
Erweiterung ist damit realistisch eine Vorführung, kein Werkzeug, das er
nächste Woche produktiv nutzt — das gehört so in die Arbeit und ist ehrlicher
als die Behauptung des Gegenteils.
