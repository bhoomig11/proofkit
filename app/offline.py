"""Deterministic offline replay LLM for the five synthetic personas."""
from __future__ import annotations

from typing import Any

from proofkit.common.llm import FakeLLM, LLMClient

from app.data import DemoData


def make_offline_llm(data: DemoData) -> LLMClient:
    """Replay golden extraction/earnings outputs while preserving pipeline safety checks."""
    findings_by_note: dict[str, list[dict[str, Any]]] = {}
    for bundle in data.golden_findings.values():
        for finding in bundle.findings:
            status = finding.status.value
            sloppy_status = "current" if status in {"negated", "ruled_out", "family_history"} else status
            findings_by_note.setdefault(finding.note_id, []).append({
                "condition": finding.condition,
                "icd10": finding.icd10.lower(),
                "status": sloppy_status,
                "quote": finding.quote,
                "quote_start": None,
                "quote_end": None,
                "confidence": finding.confidence,
            })

    def extract_findings(_instructions: str, untrusted_text: str | None) -> dict[str, Any]:
        text = untrusted_text or ""
        for items in findings_by_note.values():
            if items and all(item["quote"] in text for item in items):
                return {"findings": items}
        return {"findings": []}

    records_by_document: dict[str, list[dict[str, Any]]] = {}
    for records in data.golden_records.values():
        for record in records:
            records_by_document.setdefault(record.source_doc_id, []).append({
                "platform": record.platform.upper(),
                "period_start": record.period_start.isoformat(),
                "period_end": record.period_end.isoformat(),
                "hours": None if record.hours is None else str(record.hours),
                "gross_income": str(record.gross_income),
                "source_quote": record.source_quote,
                "confidence": record.confidence,
            })

    def extract_earnings(_instructions: str, untrusted_text: str | None) -> dict[str, Any]:
        text = untrusted_text or ""
        for items in records_by_document.values():
            if items and all(item["source_quote"] in text for item in items):
                return {"records": items}
        return {"records": []}

    return FakeLLM({
        "extract_findings": extract_findings,
        "extract_earnings": extract_earnings,
        "draft_statement": {"summary": "The record documents the conditions shown in the evidence."},
    })
