"""
Code/quote consistency: a code that would count toward an exemption must be backed by the words of its quote.

Grounding proves the quote is in the note; it does not prove the LLM's ICD-10 code fits that quote. If a code
matches a frailty rule, the quote's sentence must contain one of that rule's `terms` (config/frailty_rules.json).
Words are compared by stem (first 6 letters), so "malignancy" also covers "malignant". The pipeline uses this only
to DOWNGRADE current -> uncertain, which routes the finding to clinician review instead of counting it.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

FRAILTY_RULES = Path(__file__).resolve().parents[3] / "config" / "frailty_rules.json"
STEM = 6


def _stems(text: str) -> list[str]:
    return [w[:STEM] for w in re.findall(r"[a-z0-9]+", text.lower())]


@lru_cache(maxsize=1)
def _rules() -> tuple[tuple[tuple[str, ...], tuple[tuple[str, ...], ...]], ...]:
    """(icd10 prefixes, term stems) per rule. Rules without `terms` fall back to their label."""
    rules = json.loads(FRAILTY_RULES.read_text())["rules"]
    return tuple((tuple(r["icd10_prefixes"]), tuple(tuple(_stems(t)) for t in r.get("terms") or [r["label"]]))
                 for r in rules)


def code_supported(icd10: str, sentence: str) -> bool:
    """False only when `icd10` matches a frailty rule and none of that rule's terms appear in `sentence`."""
    words = _stems(sentence)
    matching = [terms for prefixes, terms in _rules() if any(icd10.startswith(p) for p in prefixes)]
    if not matching:
        return True
    return any(all(any(w.startswith(s) for w in words) for s in term) for terms in matching for term in terms)
