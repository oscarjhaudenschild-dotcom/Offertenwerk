"""Gold standard test cases for RAG evaluation."""

import json
import os
from typing import List, Dict


class GoldSet:
    """
    Gold standard: test cases with known correct answers.

    Each test case contains:
    - scenario: description of the situation
    - query: what we ask the RAG
    - expected_answer: correct answer (for factual accuracy check)
    - expected_chunks: which chunks SHOULD be retrieved (for diagnostic eval)
    """

    def __init__(self, path: str = "./measurements/gold_set.json"):
        self.path = path
        self.cases = self._load_or_create()

    def _load_or_create(self) -> List[Dict]:
        """Load gold set from disk or create empty list."""
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except:
                return []
        return []

    def save(self):
        """Save gold set to disk."""
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.cases, f, indent=2)

    def add_case(
        self,
        case_id: str,
        scenario: str,
        query: str,
        expected_answer: str,
        expected_chunk_ids: List[str] = None,
        category: str = "general"
    ):
        """Add a test case to the gold set."""
        self.cases.append({
            "case_id": case_id,
            "scenario": scenario,
            "query": query,
            "expected_answer": expected_answer,
            "expected_chunk_ids": expected_chunk_ids or [],
            "category": category
        })
        self.save()

    def get_cases(self, category: str = None) -> List[Dict]:
        """Get all test cases, optionally filtered by category."""
        if category:
            return [c for c in self.cases if c.get("category") == category]
        return self.cases

    def get_case(self, case_id: str) -> Dict:
        """Get specific test case."""
        for case in self.cases:
            if case["case_id"] == case_id:
                return case
        return None

    @staticmethod
    def create_bootstrap_gold_set() -> List[Dict]:
        """
        Demo gold set matching CorpusBuilder.create_bootstrap_corpus().

        expected_chunk_ids assume each bootstrap document fits in one chunk,
        which holds at the default chunk size. These five cases exist to prove
        the harness works; the thesis needs 25-30 written against the real corpus.
        """
        return [
            {
                "case_id": "PA_001",
                "scenario": "Firma mit 5 Mitarbeitenden",
                "query": "Wie hoch sind die Kosten der Personaladministration bei fünf Mitarbeitenden?",
                "expected_answer": "CHF 900 pro Mitarbeiter und Jahr (Stufe 3 bis 7)",
                "expected_chunk_ids": ["doc_personnel_tiers_chunk_0"],
                "category": "personaladministration",
            },
            {
                "case_id": "PA_002",
                "scenario": "Startup mit 2 Mitarbeitenden",
                "query": "Was kostet die Personaladministration bei zwei Mitarbeitenden?",
                "expected_answer": "CHF 1000 pro Mitarbeiter und Jahr (Stufe 1 bis 2)",
                "expected_chunk_ids": ["doc_personnel_tiers_chunk_0"],
                "category": "personaladministration",
            },
            {
                "case_id": "RATE_001",
                "scenario": "Frage nach dem Stundenansatz",
                "query": "Welcher Stundenansatz gilt für einen diplomierten Treuhandexperten?",
                "expected_answer": "CHF 250 pro Stunde",
                "expected_chunk_ids": ["doc_hourly_rates_chunk_0"],
                "category": "stundenansaetze",
            },
            {
                "case_id": "BK_001",
                "scenario": "Aufwandschätzung laufende Buchführung",
                "query": "Wie viele Buchungen werden pro Stunde angenommen?",
                "expected_answer": "50 Buchungen pro Stunde",
                "expected_chunk_ids": ["doc_bookkeeping_chunk_0"],
                "category": "buchhaltung",
            },
            {
                "case_id": "MWST_001",
                "scenario": "Frage zur Mehrwertsteuer",
                "query": "Ab welchem Jahresumsatz besteht Mehrwertsteuerpflicht?",
                "expected_answer": "Ab CHF 100000 Jahresumsatz, Normalsatz 8.1 Prozent",
                "expected_chunk_ids": ["doc_mwst_chunk_0"],
                "category": "mwst",
            },
            {
                "case_id": "FORM_001",
                "scenario": "Neugründung einer Gesellschaft",
                "query": "Was kostet die Gründung einer Gesellschaft?",
                "expected_answer": "CHF 2000 bis CHF 2500 inklusive Notar- und Handelsregistergebühren",
                "expected_chunk_ids": ["doc_formation_chunk_0"],
                "category": "gruendung",
            },
        ]
