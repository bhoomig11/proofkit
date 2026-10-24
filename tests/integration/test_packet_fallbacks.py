"""Focused examples for invalid-offset and missing-note evidence fallbacks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape
from html.parser import HTMLParser

import pytest

from proofkit.contracts import (
    ClinicalNote,
    Finding,
    FindingStatus,
    Member,
    OverallStatus,
    ProofKitStatus,
)
from proofkit.integration.packet import render_packet


MEMBER_ID = "SYN-0001"


class FallbackParser(HTMLParser):
    """Collect decoded marks, list items, and visible packet text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.mark_texts: list[str] = []
        self.list_item_texts: list[str] = []
        self.visible_text: list[str] = []
        self._mark_chunks: list[str] | None = None
        self._list_item_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized_tag = tag.lower()
        if normalized_tag == "mark":
            self._mark_chunks = []
        elif normalized_tag == "li":
            self._list_item_chunks = []

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "mark" and self._mark_chunks is not None:
            self.mark_texts.append("".join(self._mark_chunks))
            self._mark_chunks = None
        elif normalized_tag == "li" and self._list_item_chunks is not None:
            self.list_item_texts.append("".join(self._list_item_chunks))
            self._list_item_chunks = None

    def handle_data(self, data: str) -> None:
        self.visible_text.append(data)
        if self._mark_chunks is not None:
            self._mark_chunks.append(data)
        if self._list_item_chunks is not None:
            self._list_item_chunks.append(data)


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Fallback Test Member",
        renewal_date=date(2025, 12, 31),
    )


def _status() -> ProofKitStatus:
    return ProofKitStatus(member_id=MEMBER_ID, status=OverallStatus.NEEDS_REVIEW)


def _note(text: str, *, note_id: str = "note-present") -> ClinicalNote:
    return ClinicalNote(
        note_id=note_id,
        member_id=MEMBER_ID,
        note_date=date(2025, 1, 2),
        text=text,
    )


def _finding(
    quote: str,
    *,
    note_id: str,
    quote_start: int,
    finding_id: str,
) -> Finding:
    return Finding(
        finding_id=finding_id,
        note_id=note_id,
        note_date=date(2025, 1, 2),
        condition="Test condition",
        icd10="M32.9",
        status=FindingStatus.CURRENT,
        quote=quote,
        quote_start=quote_start,
        quote_end=quote_start + len(quote),
        confidence=Decimal("0.99"),
    )


def _parse(document: str) -> FallbackParser:
    parser = FallbackParser()
    parser.feed(document)
    parser.close()
    return parser


_MISMATCH_QUOTE = '<move & "this">'
_MISMATCH_NOTE_TEXT = f"{_MISMATCH_QUOTE} then same-size-wrong"
_INVALID_SAME_NOTE_CASES = (
    pytest.param("short note", "<end & beyond>", 8, id="end-beyond-note"),
    pytest.param("short note", "<starts & late>", len("short note"), id="start-at-note-length"),
    pytest.param(
        _MISMATCH_NOTE_TEXT,
        _MISMATCH_QUOTE,
        _MISMATCH_NOTE_TEXT.index("same-size-wrong"),
        id="in-bounds-substring-mismatch",
    ),
)


@pytest.mark.parametrize(
    ("note_text", "quote", "quote_start"),
    _INVALID_SAME_NOTE_CASES,
)
def test_invalid_same_note_offsets_render_one_standalone_escaped_quote(
    note_text: str,
    quote: str,
    quote_start: int,
) -> None:
    """Validates: Requirements 5.4, 5.5."""
    note = _note(note_text)
    finding = _finding(
        quote,
        note_id=note.note_id,
        quote_start=quote_start,
        finding_id="finding-invalid",
    )

    document = render_packet(
        _member(),
        _status(),
        findings=[finding],
        notes=[note],
    )
    parser = _parse(document)

    escaped_quote = escape(quote, quote=True)
    assert parser.mark_texts == []
    assert parser.list_item_texts == [quote]
    assert document.count(escaped_quote) == note.text.count(quote) + 1
    assert f"Note ID: {note.note_id}" not in "".join(parser.visible_text)


def test_missing_note_quotes_are_standalone_escaped_labelled_and_ordered() -> None:
    """Validates: Requirement 5.6."""
    supplied_note = _note("Only the supplied note is rendered.")
    missing_evidence = (
        ('missing-<&-"one"', '<first & "quote">'),
        ("missing-two", "<second & quote>"),
    )
    findings = [
        _finding(
            quote,
            note_id=note_id,
            quote_start=0,
            finding_id=f"finding-missing-{ordinal}",
        )
        for ordinal, (note_id, quote) in enumerate(missing_evidence)
    ]

    document = render_packet(
        _member(),
        _status(),
        findings=findings,
        notes=[supplied_note],
    )
    parser = _parse(document)

    assert parser.mark_texts == []
    assert len(parser.list_item_texts) == len(missing_evidence)
    for item_text, (note_id, quote) in zip(
        parser.list_item_texts,
        missing_evidence,
        strict=True,
    ):
        assert f"Note ID: {note_id}" in item_text
        assert quote in item_text
        assert escape(note_id, quote=True) in document
        assert document.count(escape(quote, quote=True)) == 1

    assert f"Note ID: {supplied_note.note_id}" not in "".join(parser.visible_text)


def test_same_note_fallbacks_keep_finding_order_without_duplicate_valid_evidence() -> None:
    """Validates: Requirements 5.4, 5.5."""
    note = _note("VALID evidence in the source note")
    first_quote = "<first fallback>"
    second_quote = "<second & fallback>"
    first_fallback = _finding(
        first_quote,
        note_id=note.note_id,
        quote_start=len(note.text),
        finding_id="finding-first-fallback",
    )
    valid_finding = _finding(
        "VALID",
        note_id=note.note_id,
        quote_start=0,
        finding_id="finding-valid",
    )
    second_fallback = _finding(
        second_quote,
        note_id=note.note_id,
        quote_start=len(note.text) + 5,
        finding_id="finding-second-fallback",
    )

    document = render_packet(
        _member(),
        _status(),
        findings=[first_fallback, valid_finding, second_fallback],
        notes=[note],
    )
    parser = _parse(document)

    assert parser.mark_texts == ["VALID"]
    assert parser.list_item_texts == [first_quote, second_quote]
    assert document.count(escape(first_quote, quote=True)) == 1
    assert document.count(escape(second_quote, quote=True)) == 1
    assert document.count(escape(valid_finding.quote, quote=True)) == 1
