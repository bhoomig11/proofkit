"""
FINAL: offline demo mode (.kiro/specs/offline-demo).

`demo_llm()` returns a `FakeLLM` that replays recorded answers built from the golden fixtures, so every persona
runs through the public module APIs with no API key and no network. `choose_llm()` picks the demo client or the
live `AnthropicClient`.

Routing is pure and fixture-only: a reply is chosen by matching the untrusted text against fixture sources (exact
text first, else the single fixture source the text contains; ambiguity gives no items), and its items are always copied from the golden fixtures,
never from the untrusted text. Untrusted text never reaches `instructions` (FakeLLM keeps it in the delimited
user block).
"""
from __future__ import annotations

import base64
import binascii
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from proofkit.common.config import load_settings
from proofkit.common.llm import AnthropicClient, FakeLLM, LLMClient, LLMError
from proofkit.common.redact import get_logger
from proofkit.contracts import (
    ClinicalNote,
    DocumentType,
    EarningsDocument,
    EarningsRecord,
    Finding,
    FindingsBundle,
)

__all__ = ["DEFAULT_FIXTURES_DIR", "DEMO_SUMMARY", "MODE_LABELS", "choose_llm", "demo_llm"]

DEFAULT_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"
DEMO_SUMMARY = (
    "The findings listed above are documented in the cited clinical notes. Each is shown with the exact quote "
    "from the record for the reviewing clinician to confirm."
)
MODE_LIVE = "live"
MODE_DEMO = "offline-demo"
MODE_LABELS: Mapping[str, str] = MappingProxyType({MODE_LIVE: "Live LLM", MODE_DEMO: "Offline demo (recorded answers)"})
DEMO_ENV = "PROOFKIT_DEMO"
DEMO_ENV_ON = "1"
_BINARY_TYPES = (DocumentType.PDF, DocumentType.IMAGE)

# Fixture collections: (subdirectory, glob). Each must exist and hold at least one file.
_NOTES = ("notes", "*.json")
_DOCS = ("earnings_docs", "*.json")
_FINDINGS = ("findings", "*.golden.json")
_EARNINGS = ("earnings", "*.golden.json")

log = get_logger(__name__)

Items = tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class _Source:
    """One replayable fixture source: its exact text, its fixture id and the golden items recorded for it."""

    text: str
    source_id: str
    items: Items


# ─────────────────────────── fixture loading ───────────────────────────
def _invalid(path: Path, root: Path) -> ValueError:
    """-> ValueError naming only the fixture file, relative to the fixtures dir (never its contents)."""
    try:
        name = path.relative_to(root).as_posix()
    except ValueError:
        name = path.name
    return ValueError(f"demo fixture {name} is invalid")


def _collection(root: Path, spec: tuple[str, str]) -> list[Path]:
    """-> sorted files of one fixture collection. Raises ValueError naming the missing or empty directory."""
    sub, pattern = spec
    directory = root / sub
    paths = sorted(directory.glob(pattern)) if directory.is_dir() else []
    if not paths:
        raise ValueError(f"demo fixtures directory {sub} is missing or empty")
    return paths


def _load_models(paths: list[Path], root: Path, parse: Callable[[Any], list[Any]]) -> list[Any]:
    """Read and validate each file with `parse`. Any error becomes a ValueError naming only the file.

    The ValueError is raised outside the `except` block, so no original exception (which may quote file
    content) is chained as __cause__ or __context__.
    """
    out: list[Any] = []
    for path in paths:
        parsed: list[Any] | None = None
        try:
            parsed = parse(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError,
                binascii.Error):
            parsed = None
        if parsed is None:
            raise _invalid(path, root)
        out += parsed
    return out


def _doc_text(doc: EarningsDocument) -> str | None:
    """EarningsDocument -> the text P2 would send to the LLM, or None for binary types.

    Raises binascii.Error / UnicodeDecodeError for bad base64; the loader turns those into a file-named ValueError.
    """
    if doc.doc_type in _BINARY_TYPES:
        return None
    if doc.content_text is not None:
        return doc.content_text
    return base64.b64decode(doc.content_b64 or "", validate=True).decode("utf-8")


def _parse_doc(data: Any) -> list[tuple[EarningsDocument, str | None]]:
    """JSON -> [(EarningsDocument, its text)], decoding text at load time so errors name the file."""
    doc = EarningsDocument.model_validate(data)
    return [(doc, _doc_text(doc))]


def _finding_item(f: Finding) -> dict[str, Any]:
    """Finding -> one item in the shape EXTRACTION_INSTRUCTIONS asks for, with the exact golden values."""
    return {"condition": f.condition, "icd10": f.icd10, "status": f.status.value, "quote": f.quote,
            "quote_start": f.quote_start, "quote_end": f.quote_end, "confidence": f.confidence}


def _record_items(records: list[EarningsRecord]) -> Items:
    """EarningsRecord[] of one document -> statement items, merging records split from one (doc, quote)."""
    groups: dict[str, list[EarningsRecord]] = {}
    for r in records:
        groups.setdefault(r.source_quote, []).append(r)
    items = []
    for quote, recs in groups.items():
        known_hours = [r.hours for r in recs if r.hours is not None]
        hours = sum(known_hours, Decimal("0")) if known_hours else None
        income = sum((r.gross_income for r in recs), Decimal("0"))
        items.append({
            "platform": recs[0].platform.upper(),
            "period_start": min(r.period_start for r in recs).isoformat(),
            "period_end": max(r.period_end for r in recs).isoformat(),
            "hours": None if hours is None else str(hours),
            "gross_income": str(income),
            "source_quote": quote,
            "confidence": min(r.confidence for r in recs),
        })
    return tuple(items)


def _sources(root: Path) -> tuple[tuple[_Source, ...], tuple[_Source, ...]]:
    """Fixtures dir -> (note sources, document sources). Raises ValueError naming a missing dir or bad file."""
    if not root.is_dir():
        raise ValueError(f"demo fixtures directory {root.name} is missing")
    note_paths, doc_paths = _collection(root, _NOTES), _collection(root, _DOCS)
    finding_paths, earning_paths = _collection(root, _FINDINGS), _collection(root, _EARNINGS)

    notes: list[ClinicalNote] = _load_models(note_paths, root, lambda d: [ClinicalNote.model_validate(d)])
    docs: list[tuple[EarningsDocument, str | None]] = _load_models(doc_paths, root, _parse_doc)
    bundles: list[FindingsBundle] = _load_models(finding_paths, root, lambda d: [FindingsBundle.model_validate(d)])
    records: list[EarningsRecord] = _load_models(earning_paths, root,
                                                 lambda d: [EarningsRecord.model_validate(r) for r in d])

    note_items: dict[str, list[dict[str, Any]]] = {}
    for bundle in bundles:
        for f in bundle.findings:
            note_items.setdefault(f.note_id, []).append(_finding_item(f))
    note_sources = tuple(_Source(n.text, n.note_id, tuple(note_items.get(n.note_id, ()))) for n in notes)

    doc_records: dict[str, list[EarningsRecord]] = {}
    for r in records:
        doc_records.setdefault(r.source_doc_id, []).append(r)
    doc_sources = tuple(_Source(text, doc.doc_id, _record_items(doc_records.get(doc.doc_id, [])))
                        for doc, text in docs if text is not None)
    return note_sources, doc_sources


# ─────────────────────────── replay matching ───────────────────────────
def _exact_items(candidates: list[_Source]) -> Items:
    """Exact-match candidates -> their shared items; () if they recorded different items (ambiguous)."""
    first = candidates[0].items
    return first if all(c.items == first for c in candidates[1:]) else ()


def _match(sources: tuple[_Source, ...], untrusted_text: str | None) -> Items:
    """Untrusted text -> golden items of the uniquely matching fixture source; () otherwise.

    1. Exact source text: if several exact sources recorded different items, the result is empty.
    2. Otherwise containment: exactly one fixture source whose text the untrusted text contains -> its items.
       Zero or more than one contained source -> () (fail safe; no tie-break).
    The text is only compared, never copied into the result.
    """
    text = untrusted_text or ""
    if not text:
        return ()
    exact = [s for s in sources if s.text == text]
    if exact:
        return _exact_items(exact)
    contained = [s for s in sources if s.text and s.text in text]
    return contained[0].items if len(contained) == 1 else ()


# ─────────────────────────── public API ───────────────────────────
def demo_llm(fixtures_dir: Path | None = None) -> LLMClient:
    """Fixtures (ClinicalNote, EarningsDocument, FindingsBundle, EarningsRecord) -> a replaying FakeLLM.

    Tasks: extract_findings -> {"findings": [...]}, extract_earnings -> {"records": [...]},
    draft_statement -> {"summary": DEMO_SUMMARY}. Unmatched or ambiguous text gets an empty list; unknown tasks
    raise LLMError. Raises ValueError naming the missing fixture directory or the bad fixture file.
    """
    note_sources, doc_sources = _sources(Path(fixtures_dir) if fixtures_dir is not None else DEFAULT_FIXTURES_DIR)

    def findings(_instructions: str, untrusted_text: str | None) -> dict[str, Any]:
        return {"findings": list(_match(note_sources, untrusted_text))}

    def earnings(_instructions: str, untrusted_text: str | None) -> dict[str, Any]:
        return {"records": list(_match(doc_sources, untrusted_text))}

    log.info("demo llm ready notes=%d docs=%d", len(note_sources), len(doc_sources))
    return FakeLLM({"extract_findings": findings, "extract_earnings": earnings,
                    "draft_statement": {"summary": DEMO_SUMMARY}})


def choose_llm(*, demo: bool | None = None) -> tuple[LLMClient, str]:
    """-> (LLMClient, mode) with mode in {"live", "offline-demo"}.

    demo=True: offline demo. demo=False: live (raises LLMError without a key). demo=None: PROOFKIT_DEMO == "1"
    -> demo (any other value is ignored); otherwise live when a key is configured, else demo. The key is read
    only via load_settings and is never logged.
    """
    if demo is None and os.environ.get(DEMO_ENV) == DEMO_ENV_ON:
        demo = True
    if demo:
        log.info("llm mode=%s", MODE_DEMO)
        return demo_llm(), MODE_DEMO
    settings = load_settings()
    if not settings.anthropic_api_key:
        if demo is False:
            raise LLMError("live mode requested but no API key is configured")
        log.info("llm mode=%s (no key configured)", MODE_DEMO)
        return demo_llm(), MODE_DEMO
    log.info("llm mode=%s", MODE_LIVE)
    return AnthropicClient(settings), MODE_LIVE
