"""
P1A extraction pipeline: ClinicalNote[] -> FindingsBundle.

The LLM proposes findings; this module verifies them. Every returned Finding has a valid ICD-10
code and a quote that is literally present in its note. Anything else is dropped and counted.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from proofkit.common.injection import injection_spans, overlaps_injection
from proofkit.common.llm import LLMClient
from proofkit.contracts import ClinicalNote, Finding, FindingsBundle, FindingStatus
from proofkit.extraction.ground import ground_quote
from proofkit.extraction.normalize import normalize_icd10
from proofkit.extraction.prompts import EXTRACTION_INSTRUCTIONS
from proofkit.extraction.status import apply_backstop

EXTRACTOR_VERSION = "p1a-0.1.0"

# The FakeLLM / real LLM is called with task="extract_findings" ONCE PER NOTE and must return:
# {"findings": [{"condition": str, "icd10": str, "status": str, "quote": str,
#                "quote_start": int|null, "quote_end": int|null, "confidence": float}]}
LLM_TASK = "extract_findings"


def _verify(note: ClinicalNote, raw: Any, tainted: list[tuple[int, int]]) -> dict | None:
    """Turn one raw LLM item into verified Finding fields, or None if it must be dropped."""
    if not isinstance(raw, dict):
        return None
    icd10 = normalize_icd10(raw.get("icd10"))
    span = ground_quote(note.text, raw.get("quote"), raw.get("quote_start"))
    if icd10 is None or span is None or overlaps_injection(span.start, span.end, tainted):
        return None
    try:
        status = apply_backstop(FindingStatus(raw.get("status")), note.text, span.start, span.end)
    except ValueError:
        return None
    return {"condition": raw.get("condition"), "icd10": icd10, "status": status, "quote": span.text,
            "quote_start": span.start, "quote_end": span.end, "confidence": raw.get("confidence")}


def extract_findings(notes: list[ClinicalNote], member_id: str, llm: LLMClient) -> FindingsBundle:
    """ClinicalNote[] -> FindingsBundle. Every returned Finding is grounded and has a valid ICD-10 code."""
    findings: list[Finding] = []
    processed: list[str] = []
    dropped = 0
    for note in notes:
        response = llm.complete_json(task=LLM_TASK, instructions=EXTRACTION_INSTRUCTIONS, untrusted_text=note.text)
        tainted = injection_spans(note.text)
        verified = []
        for raw in response.get("findings", []):
            fields = _verify(note, raw, tainted)
            if fields is None:
                dropped += 1
            else:
                verified.append(fields)
        for i, fields in enumerate(sorted(verified, key=lambda f: f["quote_start"])):
            try:
                findings.append(Finding(finding_id=f"F-{note.note_id}-{i}", note_id=note.note_id,
                                        note_date=note.note_date, **fields))
            except ValidationError:
                dropped += 1
        processed.append(note.note_id)
    return FindingsBundle(member_id=member_id, notes_processed=processed, findings=findings,
                          dropped_ungrounded=dropped, extractor_version=EXTRACTOR_VERSION)
