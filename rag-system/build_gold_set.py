#!/usr/bin/env python3
"""
Build the gold set from the anonymised corpus.

    python3 build_gold_set.py

Each case names a question, the document that must answer it, and an anchor -
a distinctive phrase near the answer. The script locates the chunk holding that
anchor and reads the amount out of the document itself.

Generating rather than typing matters here: anonymisation rescales every
amount, so a hand-written expected answer would drift out of step with the
corpus the moment the scaling factor changed. This way the gold set cannot
disagree with the documents it is measured against.

Cases whose anchor is not found are reported rather than written, so a silent
mismatch is impossible.
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from retrieval_core import RetrievalCore

GOLD_PATH = Path("measurements/gold_set.json")

D01 = "offerte_01_lohn_gross_anon"
D02 = "offerte_02_accounting_intl_anon"
D03 = "offerte_03_accounting_branch_anon"
D04 = "offerte_04_revision_anon"
D05 = "offerte_05_stiftung_audit_anon"
D06 = "offerte_06_gruendung_klein_anon"
D07 = "offerte_07_gruendung_domizil_anon"
D08 = "offerte_08_gruendung_vr_anon"
D09 = "offerte_09_domizil_beratung_anon"
D10 = "offerte_10_accounting_medtech_anon"
D11 = "offerte_11_swiss_finish_anon"
D12 = "offerte_12_lohn_reinigung_anon"
D13 = "offerte_13_holding_spaltung_anon"
D14 = "offerte_14_buchhaltung_klein_anon"

# Analysis categories, kept separate from the service type. The service type
# says what a case is about; this says what a failure on it would mean.
#
#   verwechselbar     the service appears in many offers at different prices;
#                     this is where the central finding lives
#   kontrolle         near-identical across the archive, so it must always be
#                     found - a failure here indicts the pipeline, not the search
#   einzelquelle      only one document can answer
#   qualitativ        no numeric anchor
#   unterspezifiziert the question does not identify one document; reported
#                     separately and excluded from the headline hit rate
#   unbeantwortbar    no document answers it
KONTROLLE = {"RATE_01", "RATE_02", "RATE_03", "RATE_04", "SETMA_01", "SETMA_02"}
UNTERSPEZIFIZIERT = {"REV_02", "AUD_02", "GRUE_01", "GRUE_02", "VR_01"}
EINZELQUELLE = {
    "BUCH_01", "BUCH_02", "BUCH_04", "BUCH_05", "BUCH_07", "BUCH_09", "BUCH_10",
    "AUD_01", "VR_02", "SONST_01", "SETUP_04", "REV_01",
}


def analysis_category(case_id: str, unanswerable: bool = False,
                      qualitative: bool = False) -> str:
    if unanswerable:
        return "unbeantwortbar"
    if qualitative:
        return "qualitativ"
    if case_id in KONTROLLE:
        return "kontrolle"
    if case_id in UNTERSPEZIFIZIERT:
        return "unterspezifiziert"
    if case_id in EINZELQUELLE:
        return "einzelquelle"
    return "verwechselbar"


# Questions with no figure to match on. The expected answer is a phrase that
# must appear in the retrieved chunk, so these are annotated by locating the
# phrase rather than by reading an amount.
QUALITATIVE = [
    # Each phrase occurs in exactly one document. An earlier version used
    # boilerplate ("internal bookkeeping system TOPAL"), which every offer and
    # every distractor repeats - those cases could not tell documents apart and
    # so tested nothing.
    ("QUAL_01", "einschraenkung", "Muster B AG",
     "What technical problem exists when integrating Topal data into Sage for Muster B AG?",
     D02, "Integration of Topal data in Sage is not so easy to accomplish"),
    ("QUAL_02", "anlass", "Muster C Ltd.",
     "Since when has the accounting of Muster C Ltd. not been done?",
     D03, "since November 2024 the accounting on SAP is not done"),
    ("QUAL_03", "unabhaengigkeit", "Muster E Foundation",
     "Why can Muster E Foundation not have both the audit and the accounting done by us?",
     D05, "either the annual audit of the financial statements or the accounting can be carried out by us"),
    ("QUAL_04", "leistung", "M. Beispiel",
     "What telephone service is included with the official domicile address?",
     D09, "we install your own telephone line"),
    ("QUAL_05", "abgrenzung", "Muster J Association",
     "Who prepares the ongoing accounting for Muster J Association?",
     D11, "The accounting will be provided by a third party"),
    ("QUAL_06", "anlass", "Muster L Capital",
     "What corporate restructuring is planned for the client of Muster L Capital?",
     D13, "tax-neutral split of the existing holding company"),
]

# (case_id, category, client label, question, document, anchor phrase)
CASES = [
    # Control cases: the same fact in several offers and in both languages.
    # If these do not hit, nothing else in the run is worth reading.
    ("RATE_02", "stundensatz", "Muster B AG",
     "What is the hourly rate for a Swiss Certified Fiduciary in the offer to Muster B AG?",
     D02, r"Swiss Certified Fiduciary \(Advanced"),
    ("RATE_03", "stundensatz", "Muster A GmbH",
     "Wie hoch ist der Stundenansatz für einen Treuhänder mit eidg. Fachausweis bei der Muster A GmbH?",
     D01, r"eidg\. FA oder ähnlicher Ausbildung"),
    ("RATE_04", "stundensatz", "Muster C Ltd.",
     "What is the hourly rate for an Accounting Assistant in the offer to Muster C Ltd.?",
     D03, r"Accounting Assistant"),
    ("SETMA_01", "setup", "Muster A GmbH",
     "Was kostet die Erfassung eines Mitarbeiters bei der Muster A GmbH?",
     D01, r"Erfassung Mitarbeiter \(Kosten pro Mitarbeiter\)"),
    ("SETMA_02", "setup", "Muster B AG",
     "What does setting up one employee cost in the offer to Muster B AG?",
     D02, r"Set-up employees \(fee per employee\)"),

    ("LOHN_01", "lohn", "Muster A GmbH",
     "Was kostet die Lohnbuchhaltung pro Mitarbeiter und Jahr in der Offerte an die Muster A GmbH?",
     D01, r"Lohnbuchhaltung, 27 Mitarbeiter"),
    ("BUCH_01", "buchhaltung", "Muster A GmbH",
     "Was kostet die jährliche Buchhaltung bei rund 3'000 bis 3'500 Transaktionen?",
     D01, r"3'000 bis 3'500 Transaktionen"),
    ("MWST_01", "mwst", "Muster A GmbH",
     "Was kostet die Mehrwertsteuer-Abrechnung jährlich in der Offerte an die Muster A GmbH?",
     D01, r"Mehrwertsteuer \(Ausfüllen"),
    ("STEU_01", "steuern", "Muster A GmbH",
     "Was kostet die Steuererklärung in der Offerte an die Muster A GmbH?",
     D01, r"Steuererklärung \(Fristverlängerung"),
    ("SETUP_01", "setup", "Muster A GmbH",
     "Was kostet die Einrichtung der Buchhaltung im TOPAL bei der Muster A GmbH?",
     D01, r"Einrichtung der Buchhaltung im TOPAL"),
    ("SETUP_02", "setup", "Muster A GmbH",
     "Was kostet die Einrichtung der Lohnbuchhaltung bei der Muster A GmbH?",
     D01, r"Einrichtung der Lohnbuchhaltung"),
    ("RATE_01", "stundensatz", "Muster A GmbH",
     "Wie hoch ist der Stundenansatz für einen dipl. Treuhandexperten in der Offerte an die Muster A GmbH?",
     D01, r"Treuhandexperte CHF"),

    ("BUCH_02", "buchhaltung", "Muster B AG",
     "What are the annual accounting services costs for around 100 transactions per year?",
     D02, r"around 100 transactions"),
    ("LOHN_02", "lohn", "Muster B AG",
     "What is the salary administration fee per employee per year in the offer to Muster B AG?",
     D02, r"Salary administration \(fee per employee/year\)"),
    ("SETUP_03", "setup", "Muster B AG",
     "What does the set-up of the accounting cost in the offer to Muster B AG?",
     D02, r"Set-up accounting"),
    ("MWST_02", "mwst", "Muster B AG",
     "What does preparing the VAT declarations cost in the offer to Muster B AG?",
     D02, r"Prepare the VAT declarations"),
    ("VERS_01", "versicherung", "Muster B AG",
     "What does assistance with arranging the insurances cost for Muster B AG?",
     D02, r"Assist to arrange the insurances"),

    ("BUCH_03", "buchhaltung", "Muster C Ltd.",
     "What are the annual accounting costs for around 200 transactions in the offer to Muster C Ltd.?",
     D03, r"around 200 transactions"),
    ("SETUP_04", "setup", "Muster C Ltd.",
     "What does merging the SAP accounting system cost in the offer to Muster C Ltd.?",
     D03, r"Merge SAP"),
    ("STEU_02", "steuern", "Muster C Ltd.",
     "What do the gain taxes cost in the offer to Muster C Ltd.?",
     D03, r"Gain taxes"),

    ("REV_01", "revision", "Muster D AG",
     "Wie hoch ist das Honorar für die eingeschränkte Revision bei der Muster D AG?",
     D04, r"schätzen wir unsere Aufwendungen zwischen"),
    ("REV_02", "revision", "Muster D AG",
     "Wie hoch ist der zusätzliche Initialaufwand im ersten Prüfungsjahr?",
     D04, r"Initialaufwand im ersten Prüfungsjahr"),

    ("AUD_01", "revision", "Muster E Foundation",
     "What does auditing the formation of the contribution in kind cost?",
     D05, r"Audit the formation of the contribution in kind:"),
    ("AUD_02", "revision", "Muster E Foundation",
     "What does the annual limited audit of the financial statements cost for the foundation?",
     D05, r"Annual limited audit of the financial statements"),
    ("LOHN_03", "lohn", "Muster E Foundation",
     "What is the salary administration fee per employee per year for Muster E Foundation?",
     D05, r"Salary administration \(fee per employee/year\) \(only if needed\)"),

    ("GRUE_01", "gruendung", "H. Beispiel",
     "Was kosten die Gründung einer Gesellschaft inklusive Notar und Handelsregister?",
     D06, r"Gesamtkosten für die Gründung"),
    ("BUCH_04", "buchhaltung", "H. Beispiel",
     "Was kostet die jährliche Buchhaltung bei 150 bis 200 Transaktionen?",
     D06, r"150 bis 200 Transaktionen"),
    ("VERS_02", "versicherung", "H. Beispiel",
     "Was kosten die Personalversicherungen in der Offerte an H. Beispiel?",
     D06, r"Personalversicherungen \(bei Bedarf\)"),

    ("GRUE_02", "gruendung", "J. Beispiel",
     "What does the company establishment cost including notary and register of commerce?",
     D07, r"Company establishment"),
    ("VR_01", "verwaltungsrat", "J. Beispiel",
     "What is the annual flat rate for the board of director and authorised signatory?",
     D07, r"Board of Director / Authorised signatory"),
    ("DOM_01", "domizil", "J. Beispiel",
     "What is the annual flat rate for the domicile address in the offer to J. Beispiel?",
     D07, r"Domicile address \(flat rate\)"),

    ("VR_02", "verwaltungsrat", "Muster F Consulting",
     "Was kostet das Mandat als Verwaltungsrat inklusive Sozialleistungen und D&O-Versicherung jährlich?",
     D08, r"Verwaltungsrat / Zeichnungsberechtigter \(inkl"),
    ("DOM_02", "domizil", "Muster F Consulting",
     "Was kostet eine Domiziladresse pro Jahr bei der Muster F Consulting?",
     D08, r"Domiziladresse betragen"),

    # The six later offers. Several answer the same question as an earlier one
    # with a different figure - the same 200 transactions cost CHF 4'000-4'500
    # in one offer and CHF 3'000-3'500 in another. Those collisions are the
    # sharpest test in the set, because only the client name distinguishes them.
    ("DOM_03", "domizil", "M. Beispiel",
     "What does the domicile address with c/o cost per year in the offer to M. Beispiel?",
     D09, r"Domicile address \(with c/o\)"),
    ("DOM_04", "domizil", "M. Beispiel",
     "What does the domicile address without c/o cost per year in the offer to M. Beispiel?",
     D09, r"Domicile address \(without c/o\)"),
    ("VR_03", "verwaltungsrat", "M. Beispiel",
     "What does the authorised signatory cost per year in the offer to M. Beispiel?",
     D09, r"Authorised signatory \(only if needed\)"),
    ("BUCH_05", "buchhaltung", "M. Beispiel",
     "What do the annual accounting services cost for around 250 transactions per year?",
     D09, r"around 250 transactions"),

    ("BUCH_06", "buchhaltung", "Muster I AG",
     "What do the annual accounting services cost for around 200 transactions in the offer to Muster I AG?",
     D10, r"around 200 transactions"),
    ("LOHN_04", "lohn", "Muster I AG",
     "What is the salary administration fee per employee per year in the offer to Muster I AG?",
     D10, r"Salary administration \(fee per employee/year\)"),

    ("BUCH_07", "buchhaltung", "Muster J Association",
     "What do the annual accounting services for the Swiss finish cost?",
     D11, r"Accounting services in regards of the Swiss finish"),
    ("MWST_03", "mwst", "Muster J Association",
     "What does preparing the VAT declarations cost in the offer to Muster J Association?",
     D11, r"Prepare the VAT declarations"),
    ("SETUP_05", "setup", "Muster J Association",
     "What does setting up an employee cost in the offer to Muster J Association?",
     D11, r"Set-up employees \(fee per employee\)"),

    ("BUCH_08", "buchhaltung", "Muster K Reinigungen",
     "Was kostet die jährliche Buchhaltung bei rund 200 Transaktionen in der Offerte an die Muster K Reinigungen?",
     D12, r"200 Transaktionen"),
    ("LOHN_05", "lohn", "Muster K Reinigungen",
     "Was kostet die Lohnbuchhaltung pro Mitarbeiter und Jahr bei der Muster K Reinigungen?",
     D12, r"Lohnbuchhaltung \(pro Mitarbeiter und Jahr\)"),
    ("SETUP_06", "setup", "Muster K Reinigungen",
     "Was kostet die Einrichtung der Lohnbuchhaltung bei der Muster K Reinigungen?",
     D12, r"Einrichtung der Lohnbuchhaltung"),

    ("BUCH_09", "buchhaltung", "Muster L Capital",
     "What do the annual accounting services cost for around 150 transactions per year?",
     D13, r"around 150 transactions"),
    ("SONST_01", "sonstiges", "Muster L Capital",
     "What does preparing the interim financial statement for the demerger cost?",
     D13, r"interim financial statement in 2025"),

    ("BUCH_10", "buchhaltung", "Muster M AG",
     "Was kostet die jährliche Buchhaltung bei rund 50 Transaktionen pro Jahr?",
     D14, r"50 Transaktionen"),
    ("STEU_03", "steuern", "Muster M AG",
     "Was kostet die Steuererklärung in der Offerte an die Muster M AG?",
     D14, r"Steuererklärung \(Fristverlängerung"),
]

# No document answers these. The correct behaviour is to say so.
UNANSWERABLE = [
    ("UNB_01", "unbeantwortbar",
     "Was kostet die Verwaltung einer Liegenschaft pro Jahr?"),
    ("UNB_02", "unbeantwortbar",
     "Wie hoch ist der Stundenansatz für IT-Beratung und Systembetreuung?"),
    ("UNB_03", "unbeantwortbar",
     "Welche Kosten entstehen für die Durchführung einer Betreibung?"),
    ("UNB_04", "unbeantwortbar",
     "Was kostet die Erstellung eines Businessplans für eine Bankfinanzierung?"),
    ("UNB_05", "unbeantwortbar",
     "Wie hoch ist der Rabatt bei Vorauszahlung des Jahreshonorars?"),
]

AMOUNT = re.compile(r"CHF\s*[\d'’]+(?:\s*[-–]\s*(?:CHF\s*)?[\d'’]+)?")


def locate(core: RetrievalCore, document: str, anchor: str) -> Optional[Dict]:
    """
    Find the amount in the full document, then the chunk that carries it.

    Reading from the whole document rather than from one chunk matters: a
    label and its price can land in different chunks, and anchoring the case
    to the chunk holding the label would mark a retrieval correct that never
    returned the figure.
    """
    source = Path("corpus") / f"{document}.txt"
    if not source.exists():
        return None
    text = source.read_text(encoding="utf-8")

    match = re.search(anchor, text)
    if not match:
        return None

    # The line holding the anchor comes first. Both layouts in this archive put
    # the figure on the same line as its label - the cost tables after it
    # ("Set-up accounting: CHF 1'300"), the English rate list before it
    # ("CHF 210/h Swiss Certified Fiduciary"). Searching forward alone took the
    # next line's figure for every rate; searching by nearest distance took the
    # previous line's for every cost row. The line is the unit that is right in
    # both cases.
    line_start = text.rfind("\n", 0, match.start()) + 1
    line_end = text.find("\n", match.end())
    if line_end == -1:
        line_end = len(text)

    found = AMOUNT.search(text, line_start, line_end)
    if not found:
        # Wrapped rows: the figure sits a line or two below its description.
        found = AMOUNT.search(text, line_end, line_end + 250)
    if not found:
        return None

    amount = found.group(0).strip()
    # A distinctive tail around the amount pins the right chunk even when the
    # same figure appears elsewhere in the document.
    tail = re.sub(r"\s+", " ", text[max(match.end(), found.start() - 60):found.end()]).strip()

    chunks = [c for c in core.corpus if c.get("doc_id") == document]
    for chunk in chunks:
        flat = re.sub(r"\s+", " ", chunk.get("text", ""))
        if tail and tail in flat:
            return {"amount": amount, "chunk_id": chunk["chunk_id"]}
    for chunk in chunks:
        if amount in chunk.get("text", ""):
            return {"amount": amount, "chunk_id": chunk["chunk_id"]}
    return None


def main() -> int:
    # --strip-letterhead builds the gold set against the same chunking the
    # letterhead-comparison run measures against. expected_chunk_ids are chunk
    # positions, and removing the opening block shifts word counts enough to
    # move a boundary here and there - reusing the un-stripped gold set would
    # silently compare two different chunkings against one set of answers.
    strip = "--strip-letterhead" in sys.argv
    out_path = Path("measurements/gold_set_no_letterhead.json") if strip else GOLD_PATH
    core = RetrievalCore(embedding_backend="hash", strip_letterhead=strip)
    core.load_directory("corpus")

    cases: List[Dict] = []
    missing: List[str] = []

    for case_id, category, client, query, document, anchor in CASES:
        hit = locate(core, document, anchor)
        if hit is None:
            missing.append(f"{case_id}: Anker oder Betrag nicht gefunden in {document}")
            continue
        cases.append({
            "case_id": case_id,
            "category": category,
            "kategorie": analysis_category(case_id),
            "scenario": f"Offerte an {client}",
            "query": query,
            "expected_answer": hit["amount"],
            "expected_document": document,
            "expected_chunk_ids": [hit["chunk_id"]],
            "unanswerable": False,
        })

    for case_id, category, client, query, document, phrase in QUALITATIVE:
        chunk = next((c for c in core.corpus
                      if c.get("doc_id") == document and phrase in c.get("text", "")), None)
        if chunk is None:
            missing.append(f"{case_id}: Phrase nicht in einem Chunk von {document}")
            continue
        cases.append({
            "case_id": case_id,
            "category": category,
            "kategorie": analysis_category(case_id, qualitative=True),
            "scenario": f"Offerte an {client}",
            "query": query,
            "expected_answer": phrase,
            "expected_document": document,
            "expected_chunk_ids": [chunk["chunk_id"]],
            "unanswerable": False,
        })

    for case_id, category, query in UNANSWERABLE:
        cases.append({
            "case_id": case_id,
            "category": category,
            "kategorie": analysis_category(case_id, unanswerable=True),
            "scenario": "In keiner Offerte enthalten",
            "query": query,
            "expected_answer": "nicht in den Unterlagen",
            "expected_document": None,
            "expected_chunk_ids": [],
            "unanswerable": True,
        })

    if missing:
        print("Nicht erzeugt:")
        for line in missing:
            print(f"  {line}")
        print()

    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(
        json.dumps(cases, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    answerable = sum(1 for c in cases if not c["unanswerable"])
    print(f"{len(cases)} Faelle geschrieben nach {out_path}")
    print(f"  {answerable} beantwortbar, {len(cases) - answerable} unbeantwortbar")
    by_doc: Dict[str, int] = {}
    for c in cases:
        key = c["expected_document"] or "(keines)"
        by_doc[key] = by_doc.get(key, 0) + 1
    from collections import Counter
    print("\nFaelle je Analysekategorie:")
    kc = Counter(c["kategorie"] for c in cases)
    for k in ["verwechselbar","kontrolle","einzelquelle","qualitativ",
              "unterspezifiziert","unbeantwortbar"]:
        mark = "  << unter 5" if k == "kontrolle" and kc[k] < 5 else ""
        print(f"  {k:18} {kc[k]:>3}{mark}")

    print("\nFaelle je Dokument:")
    for doc, count in sorted(by_doc.items()):
        print(f"  {count:2}  {doc}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
