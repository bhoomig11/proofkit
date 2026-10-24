"""
P1A extraction pipeline: ClinicalNote[] -> FindingsBundle.

The LLM proposes findings; this module verifies them. Every returned Finding has a valid ICD-10
code, a quote that is literally present in its note and outside injected text, and a status at
least as conservative as the deterministic backstop. Anything else is dropped and counted.
"""
from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from proofkit.common.injection import injection_spans, looks_like_injection, overlaps_injection
from proofkit.common.llm import LLMClient, LLMError
from proofkit.common.redact import get_logger
from proofkit.contracts import ClinicalNote, Finding, FindingsBundle, FindingStatus
from proofkit.extraction.consistency import code_supported
from proofkit.extraction.ground import ground_quote
from proofkit.extraction.normalize import normalize_icd10
from proofkit.extraction.prompts import EXTRACTION_INSTRUCTIONS
from proofkit.extraction.status import apply_backstop, sentence_bounds

EXTRACTOR_VERSION = "p1a-0.1.0"

# The FakeLLM / real LLM is called with task="extract_findings" ONCE PER NOTE and must return:
# {"findings": [{"condition": str, "icd10": str, "status": str, "quote": str,
#                "quote_start": int|null, "quote_end": int|null, "confidence": float}]}
LLM_TASK = "extract_findings"
MAX_ATTEMPTS = 2  # one call, plus one retry on LLMError or a malformed response
_PENDING_ID = "pending"

log = get_logger(__name__)


def _call_llm(llm: LLMClient, note: ClinicalNote) -> list | None:
    """Return the raw findings list for one note, or None after MAX_ATTEMPTS failures."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = llm.complete_json(task=LLM_TASK, instructions=EXTRACTION_INSTRUCTIONS,
                                         untrusted_text=note.text)
            if not isinstance(response, dict) or not isinstance(response.get("findings"), list):
                raise LLMError('response is not {"findings": [...]}')
            return response["findings"]
        except Exception as exc:  # any client failure (LLMError, timeout, API error) is a failed attempt
            log.warning("extract_findings failed note_id=%s attempt=%d error=%s",
                        note.note_id, attempt, type(exc).__name__)
    return None


def _clean_condition(raw: Any) -> str | None:
    """Plain, single-line, non-instruction text with tidy spacing, or None."""
    if not isinstance(raw, str) or re.search(r"[\x00-\x1f<>]", raw) or looks_like_injection(raw):
        return None
    return " ".join(raw.split()) or None


def _verify(note: ClinicalNote, raw: Any, tainted: list[tuple[int, int]]) -> Finding | None:
    """Turn one raw LLM item into a contract-valid Finding (ID assigned later), or None to drop it."""
    if not isinstance(raw, dict):
        return None
    icd10 = normalize_icd10(raw.get("icd10"))
    condition = _clean_condition(raw.get("condition"))
    confidence = raw.get("confidence")
    if icd10 is None or condition is None or isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    span = ground_quote(note.text, raw.get("quote"), raw.get("quote_start"))
    if span is None or overlaps_injection(span.start, span.end, tainted):
        return None
    try:
        status = apply_backstop(FindingStatus(raw.get("status")), note.text, span.start, span.end)
        s0, s1 = sentence_bounds(note.text, span.start, span.end)
        if status == FindingStatus.CURRENT and not code_supported(icd10, note.text[s0:s1]):
            status = FindingStatus.UNCERTAIN  # qualifying code not backed by its quote: clinician review
        return Finding(finding_id=_PENDING_ID, note_id=note.note_id, note_date=note.note_date,
                       condition=condition, icd10=icd10, status=status, quote=span.text,
                       quote_start=span.start, quote_end=span.end, confidence=confidence)
    except (ValueError, ValidationError):
        return None


def extract_findings(notes: list[ClinicalNote], member_id: str, llm: LLMClient) -> FindingsBundle:
    """ClinicalNote[] -> FindingsBundle.

    One LLM call per note (retried once). Notes that still fail are skipped and left out of
    notes_processed. Finding IDs are F-{note_id}-{i} in quote order, so they are deterministic.
    Raises ValueError if any note belongs to another member.
    """
    foreign = [n.note_id for n in notes if n.member_id != member_id]
    if foreign:
        raise ValueError(f"{len(foreign)} note(s) do not belong to {member_id}")

    findings: list[Finding] = []
    processed: list[str] = []
    dropped = 0
    for note in notes:
        raw_items = _call_llm(llm, note)
        if raw_items is None:
            log.warning("skipping note_id=%s after %d failed attempts", note.note_id, MAX_ATTEMPTS)
            continue
        tainted = injection_spans(note.text)
        unique: dict[tuple[str, int, int], Finding] = {}
        for raw in raw_items:
            finding = _verify(note, raw, tainted)
            if finding is None:
                dropped += 1
            else:
                unique.setdefault((finding.icd10, finding.quote_start, finding.quote_end), finding)
        ordered = sorted(unique.values(), key=lambda f: (f.quote_start, f.icd10))
        findings += [f.model_copy(update={"finding_id": f"F-{note.note_id}-{i}"}) for i, f in enumerate(ordered)]
        processed.append(note.note_id)
    return FindingsBundle(member_id=member_id, notes_processed=processed, findings=findings,
                          dropped_ungrounded=dropped, extractor_version=EXTRACTOR_VERSION)
