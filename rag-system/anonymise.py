#!/usr/bin/env python3
"""
Anonymise the practitioner's offers before they enter the corpus or the thesis.

    python3 anonymise.py roh/*.txt --out corpus/

The practitioner asked for confidentiality and the documents name real clients,
so this runs before anything else touches them.

Two rules shape the design:

Replacements are consistent. The same firm becomes the same pseudonym in every
document, otherwise a reader could no longer tell whether two offers concern one
client or two, and the corpus would misrepresent the archive.

Amounts are scaled by one shared factor rather than replaced individually. The
experiment depends on the relationships between figures - a rate three times
another must stay three times another. Independent replacement would destroy
exactly the structure under test.

The mapping is written to a separate file. It stays out of the thesis and out of
the corpus; it exists so you can undo the process if a document must be checked
against the original.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

# Every name pattern below uses [ \t]+ rather than \s+ on purpose. \s crosses
# line breaks, which made "Freundliche Gruesse\nMUSTER TREUHAND AG" match as one
# firm name and gave the same firm a second pseudonym - destroying exactly the
# consistency this module promises.
SP = r"[ \t]+"

# Two tiers, and the distinction matters. A legal form ends a company name for
# certain. A descriptive word like "Consulting" or "Partners" usually sits in
# the middle of one - treating both alike split "Wirz & Partners Management
# Consulting AG" into two separate firms, each with its own pseudonym.
FIRM_LEGAL = (
    r"(?:AG|GmbH|SA|Sàrl|SARL|KG|KlG|Genossenschaft|Ltd|Limited|Inc|Corp|"
    r"LLC|PLC|Stiftung|Association)\.?"
)
FIRM_DESCRIPTIVE = r"(?:Foundation|Consulting|Holding|Group|Partners|Capital)\.?"
FIRM_SUFFIX = rf"(?:{FIRM_LEGAL}|{FIRM_DESCRIPTIVE})"

# Capitalised words that can precede a firm name at the start of a sentence or
# line. Swallowing them would key the same firm twice.
LEADING_WORDS = (
    r"(?:Die|Der|Das|Den|Dem|Des|Eine|Einer|Einen|Für|Fuer|An|Von|Bei|Mit|"
    r"Und|Wir|Sie|Ihre|Ihrer|Unsere|Grüsse|Gruesse|Freundliche|Sehr|Dear|"
    r"The|Our|Your|For|With|At|To)"
)

# A name token: a capitalised word (dots allowed for "Tech."), a parenthesised
# qualifier such as "(Switzerland)", or an ampersand joining two partner names
# as in "Müller & Partners Management Consulting AG".
NAME_TOKEN = r"(?:[A-ZÄÖÜ][\w\-äöüéèàç.]*|\([A-ZÄÖÜ]\w*\)|&)"

# Applied first: run the name out to a legal form, letting descriptive words be
# part of it. Only what this leaves is then matched on a descriptive word alone,
# which is what catches "Example Consulting" and "Sample Gaming Foundation".
FIRM_PATTERN_LEGAL = re.compile(
    rf"\b(?!{LEADING_WORDS}\b)"
    rf"({NAME_TOKEN}(?:{SP}(?!{FIRM_LEGAL}(?![\w])){NAME_TOKEN}){{0,4}})"
    rf"{SP}({FIRM_LEGAL})(?![\w])"
)
FIRM_PATTERN_DESCRIPTIVE = re.compile(
    rf"\b(?!{LEADING_WORDS}\b)"
    rf"({NAME_TOKEN}(?:{SP}(?!{FIRM_SUFFIX}(?![\w])){NAME_TOKEN}){{0,3}})"
    rf"{SP}({FIRM_DESCRIPTIVE})(?![\w])"
)

# Surname is optional: "Frau Muster" at the end of a line has none, and the
# old pattern reached onto the next line to invent one.
PERSON_PATTERN = re.compile(
    rf"\b(?:Herr|Herrn|Frau|Mr|Mrs|Ms|Miss)\.?{SP}(?:Dr\.{SP})?"
    rf"([A-ZÄÖÜ][\wäöüéèàç]+)(?:{SP}([A-ZÄÖÜ][\wäöüéèàç]+))?"
)

# Salutations give only a first name: "Dear Robert", "Liebe Lisa". The
# informal German forms appear where the practitioner knows the client well,
# which is precisely where a first name stands alone with no title.
SALUTATION_PATTERN = re.compile(
    rf"\b(Dear|Sehr geehrte[rs]?|Liebe[rs]?){SP}([A-ZÄÖÜ][\wäöüéèàç]+)(?![\w])"
)

# An addressee written as a bare "Firstname Lastname" line in the letterhead,
# with no title to trigger on. Restricted to the head of the document: further
# down, a two-word capitalised line is just as likely to be "Freundliche
# Gruesse" or a section heading.
BARE_NAME_LINE = re.compile(
    r"(?m)^[ \t]*([A-ZÄÖÜ][\wäöüéèàç]+)[ \t]+([A-ZÄÖÜ][\wäöüéèàç]+)[ \t]*$"
)
HEAD_LINES = 12

STREET_PATTERN = re.compile(
    rf"\b[A-ZÄÖÜ][\wäöüéèà]*(?:strasse|straße|weg|gasse|platz|allee|ring)"
    rf"{SP}\d+[a-z]?\b",
    re.IGNORECASE,
)
# Anchored to the start of a line: an address block puts the postcode there,
# while "Zug, 15th January 2025 CK" does not. Without the anchor this turned
# every year followed by a capitalised word into a fake postcode and corrupted
# the dates in the corpus.
POSTCODE_PATTERN = re.compile(
    rf"(?m)^[ \t]*\d{{4}}{SP}([A-ZÄÖÜ][\wäöüéèà]+)"
)

# Ranges are written "CHF 15'000 - 18'000" and "CHF 160-180": only the first
# number carries the CHF. A pattern anchored on the prefix therefore scaled the
# lower bound and left the upper one at the real figure - both a leak of the
# client's actual fee and a broken ratio. The second group catches that tail.
AMOUNT_PATTERN = re.compile(
    r"\bCHF\s*([\d'’.,]+)(\s*[-–]\s*(?:CHF\s*)?([\d'’.,]+))?"
)
IBAN_PATTERN = re.compile(r"\bCH\d{2}[\s\d]{15,25}\b")
EMAIL_PATTERN = re.compile(r"\b[\w.\-]+@[\w.\-]+\.\w{2,}\b")
# No \b before the plus sign: a boundary between a space and '+' never matches,
# which silently left every international number in place.
PHONE_PATTERN = re.compile(r"(?:\+41|\b0)\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}\b")


class Anonymiser:
    def __init__(self, amount_factor: float = 0.85,
                 keep: List[str] = None, also: List[str] = None):
        self.amount_factor = amount_factor
        self.keep = {k.lower() for k in (keep or [])}
        self.also = list(also or [])
        self.firms: Dict[str, str] = {}
        self.people: Dict[str, str] = {}
        self.counts: Dict[str, int] = {
            "firms": 0, "people": 0, "amounts": 0, "ibans": 0,
            "emails": 0, "phones": 0, "addresses": 0, "also": 0,
        }

    def _firm_alias(self, name: str) -> str:
        if name not in self.firms:
            self.firms[name] = f"Muster {chr(65 + len(self.firms) % 26)}"
        return self.firms[name]

    def _person_alias(self, first: str, last: str = "") -> str:
        # A document introduces someone as "Herr Hans Muster" and refers to
        # them later as "Herr Muster". Both parts are registered against one
        # pseudonym so the two mentions stay the same person.
        keys = [k for k in (first, last) if k]
        for key in keys:
            if key in self.people:
                alias = self.people[key]
                break
        else:
            alias = f"{chr(65 + len(self.people) % 26)}. Beispiel"
        for key in keys:
            self.people[key] = alias
        return alias

    @staticmethod
    def _parse_amount(raw: str) -> float:
        cleaned = raw.replace("'", "").replace("’", "").replace(" ", "")
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)

    @staticmethod
    def _format_amount(value: float) -> str:
        # Coarser rounding on larger sums keeps them looking like quoted fees;
        # finer rounding below CHF 1'000 stops narrow ranges from collapsing.
        # At a flat 50 the hourly band "CHF 160-180" became "CHF 150-150".
        if value >= 1000:
            step = 50
        elif value >= 100:
            step = 10
        else:
            return f"{round(value, 2)}"
        return f"{int(round(value / step) * step):,}".replace(",", "'")

    def process(self, text: str) -> str:
        def firm(match: "re.Match") -> str:
            name = match.group(1)
            if name.lower() in self.keep:
                return match.group(0)
            self.counts["firms"] += 1
            return f"{self._firm_alias(name)} {match.group(2)}"

        def person(match: "re.Match") -> str:
            first, last = match.group(1), match.group(2) or ""
            if first.lower() in self.keep or f"{first} {last}".strip().lower() in self.keep:
                return match.group(0)
            self.counts["people"] += 1
            return self._person_alias(first, last)

        def salutation(match: "re.Match") -> str:
            if match.group(2).lower() in self.keep:
                return match.group(0)
            self.counts["people"] += 1
            return f"{match.group(1)} {self._person_alias(match.group(2))}"

        def amount(match: "re.Match") -> str:
            try:
                low = self._parse_amount(match.group(1))
            except ValueError:
                return match.group(0)
            self.counts["amounts"] += 1
            out = f"CHF {self._format_amount(low * self.amount_factor)}"

            if match.group(2) is None:
                return out
            try:
                high = self._parse_amount(match.group(3))
            except ValueError:
                return out + match.group(2)
            self.counts["amounts"] += 1
            separator = "-" if "-" in match.group(2) and " " not in match.group(2) else " - "
            return out + separator + self._format_amount(high * self.amount_factor)

        text = FIRM_PATTERN_LEGAL.sub(firm, text)
        text = FIRM_PATTERN_DESCRIPTIVE.sub(firm, text)
        text = PERSON_PATTERN.sub(person, text)
        text = SALUTATION_PATTERN.sub(salutation, text)

        # Bare addressee line, head of document only.
        lines = text.split("\n")
        head, rest = lines[:HEAD_LINES], lines[HEAD_LINES:]
        head_text = BARE_NAME_LINE.sub(person, "\n".join(head))
        text = "\n".join([head_text] + rest) if rest else head_text

        text = AMOUNT_PATTERN.sub(amount, text)

        def counted(pattern, key, replacement):
            nonlocal text
            text, n = pattern.subn(replacement, text)
            self.counts[key] += n

        counted(STREET_PATTERN, "addresses", "Beispielstrasse 1")
        counted(POSTCODE_PATTERN, "addresses", "0000 Musterort")
        counted(IBAN_PATTERN, "ibans", "CH00 0000 0000 0000 0000 0")
        counted(EMAIL_PATTERN, "emails", "kontakt@beispiel.ch")
        counted(PHONE_PATTERN, "phones", "+41 00 000 00 00")

        # Terms the automatic rules cannot know about - a name in flowing text,
        # a product, a place. The user names these explicitly.
        for term in self.also:
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            text, n = pattern.subn("[entfernt]", text)
            self.counts["also"] += n
        return text

    def mapping(self) -> Dict:
        return {
            "amount_factor": self.amount_factor,
            "firms": self.firms,
            "people": self.people,
            "counts": self.counts,
        }


def read_document(path: Path) -> Optional[str]:
    """
    Read .txt, .docx/.doc/.rtf or .pdf as plain text.

    Word and PDF go through conversion in a temporary file, so the unredacted
    text is never written next to the anonymised output.
    """
    suffix = path.suffix.lower()

    if suffix in {".txt", ".md"}:
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            print(f"  nicht lesbar (kein UTF-8): {path.name}")
            return None

    if suffix in {".docx", ".doc", ".rtf"}:
        if not shutil.which("textutil"):
            print(f"  {path.name}: textutil fehlt (nur macOS).")
            return None
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "converted.txt"
            result = subprocess.run(
                ["textutil", "-convert", "txt", "-output", str(out), str(path)],
                capture_output=True, text=True,
            )
            if result.returncode != 0 or not out.exists():
                print(f"  {path.name}: Umwandlung fehlgeschlagen.")
                return None
            return out.read_text(encoding="utf-8", errors="replace")

    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            print(f"  {path.name}: `pip3 install pypdf` fuer PDF-Dateien.")
            return None
        try:
            text = "\n".join(
                (page.extract_text() or "") for page in PdfReader(str(path)).pages
            )
        except Exception as exc:
            print(f"  {path.name}: Extraktion fehlgeschlagen ({exc}).")
            return None
        if not text.strip():
            print(f"  {path.name}: kein Text gefunden (vermutlich ein Scan).")
            return None
        return text

    print(f"  {path.name}: Format nicht unterstuetzt (.txt .docx .pdf).")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Anonymise offer documents")
    parser.add_argument("files", nargs="+", help="input .txt files")
    parser.add_argument("--out", default="corpus", help="output directory")
    parser.add_argument("--factor", type=float, default=0.85,
                        help="scale applied to every amount (default 0.85)")
    parser.add_argument("--mapping", default="anonymisation_mapping.json",
                        help="where to write the reversal map - keep this private")
    parser.add_argument("--keep", nargs="*", default=[],
                        help="names to leave untouched, e.g. the firm's own")
    parser.add_argument("--also", nargs="*", default=[],
                        help="extra terms to remove that no rule catches")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    anon = Anonymiser(amount_factor=args.factor, keep=args.keep, also=args.also)

    written: List[str] = []
    for raw in args.files:
        path = Path(raw)
        if not path.exists():
            print(f"  nicht gefunden: {path}")
            continue
        text = read_document(path)
        if text is None:
            continue
        target = out_dir / f"{path.stem}_anon.txt"
        target.write_text(anon.process(text), encoding="utf-8")
        written.append(str(target))
        print(f"  {path.name} -> {target}")

    Path(args.mapping).write_text(
        json.dumps(anon.mapping(), indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\n{len(written)} Datei(en) anonymisiert.")
    print("Ersetzt: " + ", ".join(f"{k}={v}" for k, v in anon.counts.items() if v))
    print(f"\nZuordnung: {args.mapping}")
    print("Diese Datei enthaelt die echten Namen. Nicht in die Arbeit, nicht ins")
    print("Korpus, nicht an einen Cloud-Dienst.")
    print("\nBitte die Ergebnisse durchlesen: Namen ohne Rechtsform-Zusatz und")
    print("Namen im Fliesstext erkennt keine Regel zuverlaessig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
