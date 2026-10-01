"""
Score generated answers against the gold standard.

Retrieval quality says whether the right document was found. It says nothing
about whether the answer built from it was correct. This module supplies the
second half: factual accuracy and the failure taxonomy the thesis reports.

Scoring is deliberately mechanical and conservative. It proposes a verdict; a
human confirms it. An automatic judge that quietly marks wrong answers correct
would be worse than no judge at all.
"""

import re
from typing import Dict, List, Optional

REFUSAL_MARKER = "nicht enthalten"


def extract_numbers(text: str) -> List[float]:
    """
    Pull monetary and numeric values out of an answer.

    Handles Swiss thousands separators (1'000, 1000, 1.000) and decimals (8.1).
    """
    if not text:
        return []
    cleaned = re.sub(r"(?<=\d)['’](?=\d)", "", text)
    values = []
    for raw in re.findall(r"\d+(?:\.\d+)?", cleaned):
        try:
            values.append(float(raw))
        except ValueError:
            continue
    return values


def score_answer(
    actual: Optional[str],
    expected: str,
    tolerance: float = 0.0,
) -> Dict:
    """
    Compare an answer against the expected one.

    tolerance is a fraction: 0.1 accepts a value within 10 percent. Default 0
    demands exact agreement, which is right for prices and rates.

    Returns a verdict plus the reason, so a disputed case can be re-checked
    rather than taken on trust.
    """
    if actual is None or not actual.strip():
        return {"verdict": "no_answer", "correct": False,
                "reason": "generation produced no text"}

    expected_numbers = extract_numbers(expected)
    actual_numbers = extract_numbers(actual)

    if REFUSAL_MARKER in actual.lower():
        # The model declined. Correct behaviour when the context genuinely
        # lacked the fact, a failure when the fact was available.
        return {"verdict": "refused", "correct": False,
                "reason": "model reported missing information"}

    if not expected_numbers:
        # Qualitative case: fall back to keyword overlap and flag for review.
        expected_words = {w for w in re.findall(r"\w{5,}", expected.lower())}
        actual_words = {w for w in re.findall(r"\w{5,}", actual.lower())}
        if not expected_words:
            return {"verdict": "needs_review", "correct": None,
                    "reason": "no numeric or lexical anchor in gold answer"}
        overlap = len(expected_words & actual_words) / len(expected_words)
        return {
            "verdict": "likely_correct" if overlap >= 0.5 else "needs_review",
            "correct": None,
            "reason": f"keyword overlap {overlap:.0%}, confirm by hand",
        }

    missing = []
    for want in expected_numbers:
        limit = abs(want) * tolerance
        if not any(abs(want - got) <= limit for got in actual_numbers):
            missing.append(want)

    if not missing:
        return {"verdict": "correct", "correct": True,
                "reason": f"all expected values present: {expected_numbers}"}

    # A confident answer carrying the wrong number is the dangerous outcome:
    # it reads as authoritative and goes out under the practitioner's name.
    if actual_numbers:
        return {
            "verdict": "wrong_value", "correct": False,
            "reason": f"expected {missing}, answer stated {actual_numbers}",
        }
    return {"verdict": "no_value", "correct": False,
            "reason": f"expected {missing}, answer contained no figures"}


def score_results(rows: List[Dict], tolerance: float = 0.0) -> List[Dict]:
    """Score every measurement row that carries a generated answer."""
    for row in rows:
        if str(row.get("generation_skipped", "")).lower() == "true":
            row["quality_rating"] = "not_generated"
            row["quality_reason"] = "run was retrieval only"
            continue
        result = score_answer(
            row.get("actual_answer"), row.get("expected_answer", ""), tolerance
        )
        row["quality_rating"] = result["verdict"]
        row["quality_reason"] = result["reason"]
    return rows


def summarise(rows: List[Dict]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        verdict = row.get("quality_rating", "unscored")
        counts[verdict] = counts.get(verdict, 0) + 1
    return counts
