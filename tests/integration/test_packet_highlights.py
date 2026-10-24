"""Focused examples for deterministic merged evidence highlights."""

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
from proofkit.integration.proof_packet import render_packet


MEMBER_ID = "SYN-0001"
Span = tuple[int, int]


class HighlightParser(HTMLParser):
    """Collect decoded mark and note text while detecting invalid mark structure."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.mark_texts: list[str] = []
        self.article_texts: list[str] = []
        self.nested_mark_count = 0
        self.adjacent_mark_count = 0
        self._mark_chunks: list[list[str]] = []
        self._article_chunks: list[str] | None = None
        self._last_article_child: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        normalized_tag = tag.lower()
        if normalized_tag == "article":
            self._article_chunks = []
            self._last_article_child = None
        elif normalized_tag == "mark":
            if self._mark_chunks:
                self.nested_mark_count += 1
            elif self._article_chunks is not None and self._last_article_child == "mark":
                self.adjacent_mark_count += 1
            self._mark_chunks.append([])

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "mark":
            chunks = self._mark_chunks.pop()
            self.mark_texts.append("".join(chunks))
            if not self._mark_chunks:
                self._last_article_child = "mark"
        elif normalized_tag == "article" and self._article_chunks is not None:
            self.article_texts.append("".join(self._article_chunks))
            self._article_chunks = None
            self._last_article_child = None

    def handle_data(self, data: str) -> None:
        if self._article_chunks is not None:
            self._article_chunks.append(data)
            if not self._mark_chunks and data:
                self._last_article_child = "text"
        for chunks in self._mark_chunks:
            chunks.append(data)


def _merge_intervals_independently(spans: list[Span]) -> list[Span]:
    """Return the interval union without using renderer implementation helpers."""
    ordered = sorted(
        enumerate(spans),
        key=lambda indexed_span: (
            indexed_span[1][0],
            indexed_span[1][1],
            indexed_span[0],
        ),
    )
    if not ordered:
        return []

    merged: list[Span] = []
    current_start, current_end = ordered[0][1]
    for _, (next_start, next_end) in ordered[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))
    return merged


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Highlight Test Member",
        renewal_date=date(2025, 12, 31),
    )


def _status() -> ProofKitStatus:
    return ProofKitStatus(member_id=MEMBER_ID, status=OverallStatus.NEEDS_REVIEW)


def _note(text: str, *, note_id: str = "note-1") -> ClinicalNote:
    return ClinicalNote(
        note_id=note_id,
        member_id=MEMBER_ID,
        note_date=date(2025, 1, 2),
        text=text,
    )


def _findings(note: ClinicalNote, spans: list[Span]) -> list[Finding]:
    return [
        Finding(
            finding_id=f"finding-{ordinal}",
            note_id=note.note_id,
            note_date=note.note_date,
            condition="Test condition",
            icd10="M32.9",
            status=FindingStatus.CURRENT,
            quote=note.text[start:end],
            quote_start=start,
            quote_end=end,
            confidence=Decimal("0.99"),
        )
        for ordinal, (start, end) in enumerate(spans)
    ]


def _parse(document: str) -> HighlightParser:
    parser = HighlightParser()
    parser.feed(document)
    parser.close()
    return parser


HIGHLIGHT_CASES: tuple[tuple[str, str, list[Span]], ...] = (
    ("disjoint", 'AA <tag>&" BB CC', [(3, 10), (14, 16)]),
    ("out-of-order", "alpha beta gamma", [(11, 16), (0, 5), (6, 10)]),
    ("duplicate", "duplicate target", [(10, 16), (10, 16), (10, 16)]),
    ("nested", "0123456789abcdef", [(2, 14), (4, 8), (6, 12)]),
    ("overlapping", "0123456789abcdef", [(1, 6), (4, 10), (8, 14)]),
    ("directly-adjacent", "0123456789abcdef", [(2, 5), (5, 9), (9, 13)]),
)


@pytest.mark.parametrize(
    ("case_name", "note_text", "source_spans"),
    HIGHLIGHT_CASES,
    ids=[case[0] for case in HIGHLIGHT_CASES],
)
def test_valid_spans_render_as_sorted_merged_marks(
    case_name: str,
    note_text: str,
    source_spans: list[Span],
) -> None:
    """Validates: Requirements 5.1, 5.2, 5.3, 12.2, 12.3."""
    del case_name
    note = _note(note_text)
    expected_spans = _merge_intervals_independently(source_spans)

    document = render_packet(
        _member(),
        _status(),
        findings=_findings(note, source_spans),
        notes=[note],
    )
    parser = _parse(document)

    expected_mark_texts = [note.text[start:end] for start, end in expected_spans]
    assert parser.mark_texts == expected_mark_texts
    assert len(parser.mark_texts) == len(expected_spans)
    assert parser.nested_mark_count == 0
    assert parser.adjacent_mark_count == 0
    assert parser.article_texts == [note.text]

    for start, end in expected_spans:
        assert f"<mark>{escape(note.text[start:end], quote=True)}</mark>" in document

    for source_start, source_end in source_spans:
        containing_spans = [
            (merged_start, merged_end)
            for merged_start, merged_end in expected_spans
            if merged_start <= source_start and source_end <= merged_end
        ]
        assert len(containing_spans) == 1


def test_notes_preserve_supplied_order_while_each_uses_its_own_highlights() -> None:
    """Validates: Requirements 5.1, 5.3."""
    first_note = _note("second supplied note", note_id="note-second")
    second_note = _note("first supplied note", note_id="note-first")
    first_spans = [(0, 6)]
    second_spans = [(6, 14)]
    findings = [
        *_findings(second_note, second_spans),
        *_findings(first_note, first_spans),
    ]

    document = render_packet(
        _member(),
        _status(),
        findings=findings,
        notes=[first_note, second_note],
    )
    parser = _parse(document)

    assert parser.article_texts == [first_note.text, second_note.text]
    assert parser.mark_texts == [
        first_note.text[first_spans[0][0] : first_spans[0][1]],
        second_note.text[second_spans[0][0] : second_spans[0][1]],
    ]
