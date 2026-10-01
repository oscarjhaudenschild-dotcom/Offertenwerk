#!/usr/bin/env python3
"""
Offertenwerk RAG - single entry point.

    python3 rag.py check                 is everything installed?
    python3 rag.py ask "deine Frage"     ask the knowledge base
    python3 rag.py experiment            run the full scaling experiment
    python3 rag.py report                build the tables for Kapitel 4
    python3 rag.py add <datei.pdf|.txt>  put a document into the corpus
    python3 rag.py anonymise <dateien>   strip names and amounts first

Everything works offline. Without Ollama the system falls back to weaker
embeddings and says so; results are then valid for testing only.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

CORPUS = Path("corpus")
MEASUREMENTS = Path("measurements")


def _run(script: str, *args: str) -> int:
    return subprocess.call([sys.executable, script, *args])


def cmd_check(_argv) -> int:
    return _run("verify_setup.py")


def cmd_ask(argv) -> int:
    if not argv:
        print('Usage: python3 rag.py ask "Wie hoch ist der Ansatz fuer einen Treuhandexperten?"')
        return 1

    from corpus_builder import CorpusBuilder
    from rag_system import RAGSystem

    question = " ".join(argv)
    builder = CorpusBuilder()
    builder.load_directory(str(CORPUS))
    docs = builder.get_documents()
    source = f"{len(docs)} Dokumente aus {CORPUS}/"
    if not docs:
        docs = CorpusBuilder.create_bootstrap_corpus()
        source = f"{len(docs)} Beispieldokumente (corpus/ ist leer)"

    rag = RAGSystem(embedding_backend="auto", enable_generation=False)
    print(f"Wissensbasis: {source}")
    rag.ingest_documents(docs)

    chunks, elapsed = rag.retrieve(question)
    print(f'\nFrage: {question}')
    print(f"Gefunden in {elapsed:.0f} ms\n")
    if not chunks:
        print("Keine passenden Stellen gefunden.")
        return 0
    for rank, chunk in enumerate(chunks, 1):
        print(f"[{rank}] {chunk['chunk_id']}  (Aehnlichkeit {chunk['similarity']:.3f})")
        text = chunk["text"]
        print(f"    {text[:280]}{'...' if len(text) > 280 else ''}\n")

    try:
        import anthropic  # noqa: F401
    except ImportError:
        print("Hinweis: fuer formulierte Antworten `pip3 install anthropic` und")
        print("ANTHROPIC_API_KEY setzen. Oben stehen die gefundenen Belegstellen.")
        return 0

    # Package present but no key is the common case after a fresh install, and
    # it used to crash inside the client instead of saying what was missing.
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Hinweis: ANTHROPIC_API_KEY ist nicht gesetzt, daher keine")
        print("formulierte Antwort. Oben stehen die gefundenen Belegstellen.")
        return 0

    rag.enable_generation = True
    print("Antwort:")
    try:
        print(rag.generate(question, chunks)["answer"])
    except Exception as exc:
        print(f"Generierung fehlgeschlagen: {exc}")
        print("Der Abruf oben ist davon unberuehrt.")
        return 1
    return 0


def cmd_experiment(argv) -> int:
    # Real corpus and real embeddings when documents are present; the demo
    # corpus only stands in when corpus/ is empty, and says so.
    if list(CORPUS.glob("*.txt")):
        default = ["--noise-levels", "10,50,100,200"]
    else:
        print("corpus/ ist leer - es laeuft der Demo-Korpus mit Ersatz-Embeddings.")
        print("Ergebnisse daraus zaehlen nicht fuer die Arbeit.\n")
        default = ["--bootstrap", "--offline", "--noise-levels", "10,50,100,200"]
    args = list(argv) or default
    print("Running both noise designs so they can be compared.\n")
    for mode in ("unrelated", "confusable"):
        print("=" * 62)
        print(f"NOISE MODE: {mode}")
        print("=" * 62)
        code = _run("run_experiment.py", *args, "--noise-mode", mode,
                    "--out", f"measurements/results_{mode}.csv")
        if code != 0:
            return code
        print()
    print("Done. Build the thesis tables with:  python3 rag.py report")
    return 0


def cmd_report(_argv) -> int:
    return _run("build_report.py")


def cmd_add(argv) -> int:
    if not argv:
        print("Usage: python3 rag.py add <datei.pdf|datei.txt>")
        return 1
    CORPUS.mkdir(exist_ok=True)
    added = 0
    for raw in argv:
        path = Path(raw)
        if not path.exists():
            print(f"  nicht gefunden: {path}")
            continue
        if path.suffix.lower() == ".pdf":
            target = CORPUS / (path.stem + ".txt")
            if not _extract_pdf(path, target):
                continue
        elif path.suffix.lower() in {".docx", ".doc", ".rtf"}:
            target = CORPUS / (path.stem + ".txt")
            if not _extract_word(path, target):
                continue
        elif path.suffix.lower() in {".txt", ".md"}:
            target = CORPUS / (path.stem + ".txt")
            shutil.copyfile(path, target)
        else:
            print(f"  uebersprungen (nur .pdf, .docx, .txt, .md): {path.name}")
            continue
        print(f"  hinzugefuegt: {target}")
        added += 1
    print(f"\n{added} Dokument(e) im Korpus. Insgesamt: {len(list(CORPUS.glob('*.txt')))}")
    return 0


def _extract_pdf(path: Path, target: Path) -> bool:
    """Extract text using whichever tool is present; say clearly if none is."""
    if shutil.which("pdftotext"):
        if subprocess.call(["pdftotext", "-layout", str(path), str(target)]) == 0:
            return True
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            print(f"  {path.name}: keine PDF-Extraktion verfuegbar.")
            print("     `pip3 install pypdf` oder `brew install poppler`,")
            print("     oder den Text von Hand als .txt speichern.")
            return False
    try:
        text = "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
    except Exception as exc:
        print(f"  {path.name}: Extraktion fehlgeschlagen ({exc})")
        return False
    if not text.strip():
        print(f"  {path.name}: kein Text gefunden (vermutlich ein Scan).")
        return False
    target.write_text(text, encoding="utf-8")
    return True


def _extract_word(path: Path, target: Path) -> bool:
    """Convert .docx/.doc/.rtf with textutil, which ships with macOS."""
    if not shutil.which("textutil"):
        print(f"  {path.name}: textutil fehlt (nur auf macOS vorhanden).")
        print("     Datei in Word oeffnen und als .txt speichern.")
        return False
    result = subprocess.run(
        ["textutil", "-convert", "txt", "-output", str(target), str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  {path.name}: Umwandlung fehlgeschlagen ({result.stderr.strip()})")
        return False
    if not target.exists() or not target.read_text(encoding="utf-8").strip():
        print(f"  {path.name}: kein Text gefunden.")
        return False
    return True


def cmd_anonymise(argv) -> int:
    if not argv:
        print("Usage: python3 rag.py anonymise roh/*.txt")
        print("Ersetzt Namen, Firmen, Betraege, IBAN, E-Mail und Telefon.")
        return 1
    return _run("anonymise.py", *argv)


COMMANDS = {
    "check": cmd_check,
    "ask": cmd_ask,
    "experiment": cmd_experiment,
    "report": cmd_report,
    "add": cmd_add,
    "anonymise": cmd_anonymise,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    command = sys.argv[1]
    if command not in COMMANDS:
        print(f"Unbekannter Befehl: {command}\n")
        print(__doc__)
        return 1
    return COMMANDS[command](sys.argv[2:])


if __name__ == "__main__":
    sys.exit(main())
