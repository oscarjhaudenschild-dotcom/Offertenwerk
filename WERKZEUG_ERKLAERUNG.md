# Offertenwerk — jeder Bestandteil erklärt

Zwei Programme, die zusammenspielen, aber unabhängig funktionieren:

1. **`app.html`** — das Formular, das der Treuhänder benutzt. Läuft immer, auch ohne RAG.
2. **`server.py`** — der optionale lokale Dienst, der die „Ähnliche Stellen"-Buttons mit Inhalt füllt.

Diese Datei geht jedes Bedienelement einzeln durch und erklärt danach die RAG-Komponente im Detail — was beim Klick technisch passiert, Zeile für Zeile.

---

## Teil 1 — Das Formular, Schritt für Schritt

### Kopfzeile
Nur der Titel „Offertenwerk". Kein Login, kein Menü — bewusst so simpel gehalten.

### Schritt 01 — Wer ist der Kunde?
| Feld | Zweck |
|---|---|
| Firma oder Name | Erscheint als Adressat im Dokument |
| Zu Handen | Ansprechpartner, zweite Zeile der Adresse |
| Anrede | Vorausgefüllt mit „Sehr geehrte Damen und Herren", frei änderbar |
| Strasse / PLZ / Ort | Adresse, erscheint im Dokument |

Kein Button hier hat mit RAG zu tun — reine Stammdaten.

### Schritt 02 — Ist eine Gründung dabei?
Ein einzelner Baustein („Modul"), der sich per Klick auf die Kopfzeile ein- und ausschaltet (Häkchen links, `tick`-Symbol). Ausgeschaltete Module verschwinden aus der Offerte und aus der Summe, bleiben aber mit ihren Werten erhalten — wieder einschalten stellt den letzten Stand her.

- **Bezeichnung in der Offerte**: der Titel, der im Dokument erscheint
- **Beschrieb**: Fliesstext — **hier setzt der „Ähnliche Stellen"-Button an**
- **Zusatzzeile**: kleiner Hinweistext unter dem Preis (z. B. „Inkl. Notar und Handelsregistergebühren")
- **Von / Bis, CHF**: die Preisspanne. Bis-Feld leer lassen → Fixpreis

### Schritt 03 — Buchhaltung und Steuern
Drei Module, alle standardmässig aktiv (`mod on`), weil praktisch jedes Mandat sie braucht.

**Buchhaltung** — das einzige Modul mit einer echten Rechnung dahinter:
- *Buchungen/Jahr* ÷ *Buchungen/Std.* = Stunden laufende Buchführung
- plus feste Stunden für Jahresabschluss und Kontrolle (Vier-Augen-Prinzip)
- plus optionale Zwischenabschlüsse
- Das Kästchen darunter (`.derived`) zeigt das Zwischenergebnis live — reine Kontrollanzeige, ändert nichts

**Steuern** — gleiche Logik, nur zwei Stundensätze (Bearbeitung + Kontrolle).

**Mehrwertsteuer** — kein Stundenaufwand, direkte Von/Bis-Eingabe.

**Bandbreite für Aufwandpositionen** (der Kasten unten): Ein Prozentsatz-Paar (Standard 95–110 %), der auf Buchhaltung und Steuern angewendet wird, damit die Offerte eine Spanne statt eines exakten Betrags zeigt. Beide Felder auf 100 setzen → Fixbetrag.

### Schritt 04 — Wie viele Mitarbeitende?
Ein Modul mit einer **Staffelpreis-Tabelle**: vier Stufen, jede mit einer Obergrenze (Anzahl Mitarbeitende) und einem CHF-Ansatz pro Kopf. Die aktive Stufe wird farblich hervorgehoben (`tier.live`), sobald die eingegebene Mitarbeiterzahl in ihren Bereich fällt. Preis = Mitarbeiterzahl × Ansatz der zutreffenden Stufe.

Aktiviert man dieses Modul, schalten sich automatisch zwei Module in Schritt 05 mit ein (Lohnbuchhaltung einrichten, Mitarbeitende erfassen) — das lässt sich danach unabhängig wieder abwählen.

### Schritt 05 — Einmalige Arbeiten
Fünf feste Module (Buchhaltung einrichten, MWST-Registrierung, Lohnbuchhaltung einrichten, Mitarbeitende erfassen, Personalversicherungen) plus:

- **„+ Eigene einmalige Position"**: erzeugt ein komplett freies Modul mit Name, Beschrieb, Von/Bis-Preis. Für alles, was die festen Module nicht abdecken.
- Jedes selbst angelegte Modul hat ein **×-Symbol** oben rechts zum Entfernen.

### Schritt 06 — Pauschalen dazu?
Verwaltungsratsmandat, Domizil/c-o-Adresse, eigene Büros — plus dieselbe „+ Eigene jährliche Position"-Funktion wie in Schritt 05.

**Ein cleverer Automatismus:** Sind Verwaltungsratsmandat *und* Domizil beide aktiv, erscheint automatisch ein viertes, unsichtbares Modul „Paketpreis statt Einzelpreise" (`mPak`), das beide zu einem Posten zusammenfasst. Abwählen zeigt wieder zwei getrennte Zeilen.

Der Domizil-Preis (`d_pr`) folgt automatisch dem Verwaltungsratsmandat (CHF 2'500 mit VR, sonst CHF 4'000) — bis man ihn einmal von Hand ändert, dann merkt sich das Feld das (`dataset.dirty`) und automatisiert nicht mehr.

### Schritt 07 — Absender und Bedingungen
Die einzigen Felder, die **dauerhaft gespeichert** werden (`localStorage`, Funktion `savePrefs()`), weil sie sich zwischen Offerten kaum ändern: eigene Firma, Stundenansätze, Standardtexte für Einleitung, Ausschlüsse, Bedingungen, Schlusswort.

- **Ihre Stundenansätze** (drei Felder): erscheinen als Autovervollständigungs-Vorschlag (`<datalist id="rates">`) in jedem CHF/Std.-Feld im ganzen Formular.
- **Mehrwertsteuer**: Dropdown, ob die Offerte MWST ausweist.

### Die Dokumentenvorschau (rechte Spalte)
Zwei Reiter:
- **„Dokument"** — was der Kunde sieht, live aus allen aktiven Modulen zusammengesetzt
- **„Rechenweg · intern"** — zeigt Stunden, Ansätze, Zwischensummen offen. Farblich abgesetzt (beige Kasten „Nur für den internen Gebrauch"), erscheint **nie** im Ausdruck oder Word-Export — das ist im Code hart verdrahtet (`buildDoc()` und `buildCalc()` sind zwei getrennte Funktionen, nur `buildDoc()` wird exportiert).

**Die drei Knöpfe unten:**
- **Drucken/PDF**: öffnet den Systemdruckdialog, aus dem sich als PDF sichern lässt
- **Word**: erzeugt eine `.doc`-Datei zum Download (echtes Word-Format mit eingebettetem CSS, kein Screenshot)
- **Neue Offerte**: leert nur die Kundendaten (Schritt 01), Absenderdaten und Standardtexte aus Schritt 07 bleiben erhalten

---

## Teil 2 — Die RAG-Komponente im Detail

Das ist der Teil, der für die Maturaarbeit zählt. Alles andere oben ist reines Formular-Handwerk ohne KI.

### Die Grundidee in einem Satz
Der Treuhänder tippt selten einen Beschrieb komplett neu — meistens hat er vor Jahren fast dasselbe schon für einen anderen Kunden formuliert. Der Button **„Ähnliche Stellen"** durchsucht sein eigenes Archiv nach genau solchen Stellen und schlägt sie vor, statt dass er selbst danach sucht.

### Woraus die Komponente besteht

```
app.html  (Browser)  ←── HTTP, nur localhost ──→  server.py  (Python)
                                                         │
                                                    retrieval_core.py
                                                         │
                                              Ollama (nomic-embed-text)
                                                         │
                                                    corpus/*.txt
                                            (14 anonymisierte alte Offerten)
```

Wichtig: **Dieselbe `retrieval_core.py`**, die hier den Server bedient, ist auch die Komponente, die im Messteil der Arbeit gemessen wird (`rag.py experiment`). Es gibt keine zweite, separate „Demo-Version" des Retrievals — was gemessen wurde, ist exakt das, was der Treuhänder benutzt.

### Schritt für Schritt: Was passiert bei einem Klick

**1. Sichtbarkeit — der `probe()`-Aufruf (app.html, Zeile ~1372)**

Sobald die Seite lädt, schickt ein unsichtbares Skript einen Test-Request an `http://127.0.0.1:8000/health`. Antwortet der Server, werden allen 18 vorgesehenen Textfeldern (`FIELDS`-Liste, z. B. `b_txt` für Buchhaltung, `d_txt` für Domizil) automatisch „Ähnliche Stellen"-Buttons angehängt. Antwortet niemand — Server nicht gestartet, Ollama nicht erreichbar — bleibt die Seite exakt wie ohne diese Erweiterung. Kein Fehler, kein leerer Knopf, einfach nichts.

**2. Klick auf „Ähnliche Stellen" — die `ask()`-Funktion**

Der Button wird deaktiviert (Doppelklick-Schutz), ein „Suche läuft…"-Hinweis erscheint, und ein `POST /similar` geht an den Server mit:
- `field`: welches Feld gefragt hat (z. B. `"d_txt"`)
- `values`: ein paar Kontext-Angaben, falls vorhanden (Kundenbranche, Mitarbeiterzahl) — **niemals ein Preis- oder Betragsfeld**, das ist im Code (`context()`) fest auf vier harmlose IDs begrenzt

**3. Auf dem Server — `build_query()` in `server.py`**

Der Server verwandelt die Anfrage in einen Suchtext:
- Kommt kein expliziter Text mit, nimmt er das **deutsche Etikett** des Feldes aus der `FIELD_LABELS`-Tabelle (z. B. für `d_txt`: *„Domizil, Domiziladresse, Postweiterleitung"*)
- Hängt die mitgeschickten Kontextwerte an

Das ist bewusst so gebaut: Ein leeres Feld liefert trotzdem eine sinnvolle Suche, weil das Etikett allein schon den fachlichen Bereich trifft.

**4. Die eigentliche Suche — `RetrievalCore.find()`**

- Der Suchtext wird mit Ollama in einen Zahlenvektor (Embedding) umgerechnet
- Dieser Vektor wird mit den Vektoren aller 36 Text-Abschnitte („Chunks") aus den 14 alten Offerten verglichen (Kosinus-Ähnlichkeit, von Hand programmiert, nicht aus einer Bibliothek — das war explizit Teil der Aufgabenstellung, damit die Messung nachvollziehbar bleibt)
- Die drei ähnlichsten Abschnitte werden zurückgegeben, jeweils mit Ähnlichkeitswert (0 bis 1)

**5. Einordnung — die `band()`-Funktion**

Jeder Treffer bekommt eine Ampel-Einstufung, nicht nur eine nackte Zahl:
| Ampel | Ähnlichkeitswert | Bedeutung |
|---|---|---|
| **hoch** | ≥ 0.75 | sehr wahrscheinlich brauchbar |
| **mittel** | 0.60 – 0.75 | prüfen, bevor übernehmen |
| **niedrig** | < 0.60 | eher nicht relevant |

Diese Schwellen stammen direkt aus der Messung: ein tatsächlich passender Textabschnitt lag im Test bei rund 0.80, ein reiner Adress-Chunk noch bei 0.67 — die Ampel macht diesen Unterschied für den Treuhänder sichtbar, ohne dass er die Zahl selbst interpretieren muss.

**6. Anzeige — die `render()`-Funktion im Browser**

Für jeden Treffer erscheint eine Karte mit Ampel-Farbe, Quelldokument-Name, dem Text selbst (bis zu ~8 Zeilen sichtbar, scrollbar) und einem Knopf **„Text übernehmen"**.

**7. Klick auf „Text übernehmen" — der wichtigste Sicherheitsschritt**

```js
var text = raw.replace(/CHF\s*[\d'’]+(?:[.,]\d+)?/g, "CHF ___");
```

Jeder CHF-Betrag im übernommenen Text wird durch `CHF ___` ersetzt, **bevor** er ins Feld eingefügt wird. Der Grund: Ein Textabschnitt aus einer alten Offerte trägt fast immer auch den damaligen Preis für diesen Kunden. Würde der unverändert übernommen, könnte ein veralteter oder falscher Betrag unbemerkt in eine neue Offerte rutschen. Der Knopf zeigt danach kurz „übernommen – Beträge entfernt" an, damit sichtbar ist, dass hier etwas entfernt wurde.

Der Text wird an bestehenden Inhalt angehängt (nicht überschrieben) und löst ein normales `input`-Ereignis aus — dadurch reagiert das Formular genauso, als hätte der Treuhänder selbst getippt, und die Livevorschau aktualisiert sich sofort.

### Was die RAG-Komponente bewusst NICHT tut

- Sie **erzeugt keinen Text** (keine Textgenerierung, kein „Schreib mir einen Absatz") — sie **findet** nur vorhandene, vom Treuhänder selbst früher geschriebene Passagen wieder.
- Sie **liest oder setzt nie ein Preisfeld** — nur die Beschrieb- und Fliesstext-Felder sind angebunden (die `FIELDS`-Liste enthält ausschliesslich Textareas, keine `type=number`-Felder).
- Sie **verlässt nie den eigenen Rechner** — keine Cloud-API, keine Internetverbindung nötig, `server.py` bindet sich explizit nur an `127.0.0.1` (Zeile `HTTPServer(("127.0.0.1", args.port), ...)`), ist also selbst im lokalen Netzwerk von aussen nicht erreichbar.
- Sie **blockiert das Formular nie** — ohne laufenden Server verschwindet nur der Button, alles andere funktioniert unverändert.

### Warum das für die Maturaarbeit relevant ist

Der Sinn dieser Konstruktion ist nicht in erster Linie der Komfort für den Treuhänder, sondern die **Einheit von Praxis und Messung**: Weil `app.html` über `server.py` dieselbe `retrieval_core.py` benutzt, die auch in `rag.py experiment` gemessen wird, beschreibt jede Zahl im Messteil der Arbeit (Trefferquote, Fehlerarten, der Briefkopf-Befund) exakt das Verhalten, das der Treuhänder in der Seitenleiste tatsächlich zu sehen bekommt — nicht das Verhalten einer separat gebauten Demo-Version.
