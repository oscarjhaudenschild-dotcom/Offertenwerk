#!/usr/bin/env python3
"""
Local retrieval service for the offer tool.

    python3 server.py --corpus corpus
    python3 server.py --corpus /pfad/zu/echten/offerten --port 8000

Serves one route to app.html's sidebar. Uses the same RetrievalCore that
`rag.py experiment` measures, so the suggestions a practitioner sees come from
the code the thesis reports on.

Nothing leaves this machine. Embeddings run through Ollama locally, and no
cloud client is imported here at all - not the Claude API, not anything else.
The corpus holds real client documents, so that is a hard boundary rather than
a default. If a drafting step is ever added, it goes through a local model in
Ollama for the same reason.

The socket binds to 127.0.0.1 only; the service is not reachable from the
network.

Standard library only, on purpose: the practitioner should not have to install
anything to run this.
"""

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from retrieval_core import RetrievalCore

# German labels per textarea id in app.html. The sidebar sends the id of the
# field the user asked from; the label becomes part of the search text so a
# query for the bookkeeping field does not drift into payroll passages.
FIELD_LABELS = {
    "g_txt": "Gründung der Gesellschaft, Notar, Handelsregister",
    "b_txt": "Buchhaltung, laufende Buchführung, Jahresabschluss",
    "s_txt": "Steuererklärung der juristischen Person",
    "mwst_txt": "Mehrwertsteuer, MWST-Abrechnung, Umsatzabstimmung",
    "p_txt": "Personaladministration, Lohnbuchhaltung, Sozialversicherungen",
    "set_buch_txt": "Einrichtung der Buchhaltung, Kontenplan",
    "set_mwst_txt": "Registrierung Mehrwertsteuer",
    "set_lohn_txt": "Einrichtung der Lohnbuchhaltung",
    "set_ma_txt": "Erfassung Mitarbeiter",
    "set_vers_txt": "Personalversicherungen, Pensionskasse, Unfallversicherung",
    "v_txt": "Verwaltungsrat, Zeichnungsberechtigter, Mandat",
    "d_txt": "Domizil, Domiziladresse, Postweiterleitung",
    "f_txt": "Revision, eingeschränkte Revision, Prüfung",
    "pk_txt": "Pauschale",
    "o_intro": "Einleitung, Bezugnahme auf das Gespräch",
    "o_ausschluss": "nicht inbegriffen, Ausschlüsse, Einsprachen",
    "o_bed": "Bedingungen, Spesen, Rechnungsstellung",
    "o_outro": "Schlusswort, Auftragserteilung",
    "o_txt": "Offerte, Honorar, Stundenansätze",
}

# Similarity bands shown as hoch/mittel/niedrig. Chosen from observed values on
# the real corpus: a correct passage scored around 0.80, while a chunk holding
# only a letterhead still reached 0.67. Below 0.60 is rarely worth showing.
BAND_HIGH = 0.75
BAND_MEDIUM = 0.60


def band(score: float) -> str:
    if score >= BAND_HIGH:
        return "hoch"
    if score >= BAND_MEDIUM:
        return "mittel"
    return "niedrig"


def build_query(payload: dict) -> str:
    """
    Turn the sidebar's request into one search text.

    An explicit query wins. Otherwise the field label anchors the topic and the
    already-filled values add the case at hand.
    """
    explicit = (payload.get("query") or "").strip()
    if explicit:
        return explicit

    parts = []
    label = FIELD_LABELS.get(payload.get("field", ""))
    if label:
        parts.append(label)

    values = payload.get("values") or {}
    if isinstance(values, dict):
        for value in values.values():
            text = str(value).strip()
            if text and text.lower() not in {"false", "true", "0"}:
                parts.append(text)

    return " ".join(parts)[:1000]


class Handler(BaseHTTPRequestHandler):
    core: RetrievalCore = None
    corpus_dir: str = "corpus"
    top_k: int = 3

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        # app.html is opened by double-click, so its origin is "null" and the
        # browser blocks the request without this header.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        if self.path.rstrip("/") != "/health":
            return self._send(404, {"error": "not found"})
        try:
            chunks = self.core.load_directory(self.corpus_dir)
        except Exception as exc:
            return self._send(503, {"ok": False, "error": str(exc)})
        self._send(200, {"ok": True, "chunks": chunks, "corpus": self.corpus_dir})

    def do_POST(self):
        if self.path.rstrip("/") != "/similar":
            return self._send(404, {"error": "not found"})

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0 or length > 100_000:
            return self._send(400, {"error": "leerer oder zu grosser Request"})
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return self._send(400, {"error": "kein gueltiges JSON"})

        query = build_query(payload if isinstance(payload, dict) else {})
        if not query.strip():
            return self._send(200, {"hits": [], "note": "zu wenig Kontext"})

        try:
            self.core.load_directory(self.corpus_dir)
            hits = self.core.find(query, k=int(payload.get("k") or self.top_k))
        except Exception as exc:
            return self._send(503, {"error": f"Suche fehlgeschlagen: {exc}"})

        for hit in hits:
            hit["level"] = band(hit["score"])
        self._send(200, {"hits": hits, "query": query})

    def log_message(self, fmt, *args):
        sys.stderr.write(f"  {self.address_string()} {fmt % args}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local retrieval service")
    parser.add_argument("--corpus", default="corpus",
                        help="directory of .txt documents to search")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("-k", type=int, default=3, help="hits to return")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        print(f"Korpus-Ordner nicht gefunden: {corpus}")
        return 1

    # Fail loudly rather than degrade: the fallback backend would return weak
    # suggestions with no sign that anything was wrong.
    try:
        core = RetrievalCore(embedding_backend="ollama")
    except RuntimeError as exc:
        print("Ollama ist nicht erreichbar.")
        print(f"  {exc}")
        print("\nOllama starten, dann erneut versuchen.")
        return 1

    print(f"Korpus wird geladen: {corpus}")
    try:
        chunks = core.load_directory(str(corpus))
    except Exception as exc:
        print(f"Laden fehlgeschlagen: {exc}")
        return 1
    print(f"  {chunks} Chunks bereit")

    Handler.core = core
    Handler.corpus_dir = str(corpus)
    Handler.top_k = args.k

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    print(f"\nBereit auf http://127.0.0.1:{args.port}")
    print("  POST /similar    Vorschlaege abrufen")
    print("  GET  /health     Verfuegbarkeit pruefen")
    print("\nNur lokal erreichbar. Keine Cloud-Dienste. Beenden mit Ctrl-C.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeendet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
