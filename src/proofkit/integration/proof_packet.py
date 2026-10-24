"""Deterministic, self-contained HTML rendering for Proof Packets."""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from proofkit.contracts import (
    ClinicalNote,
    EarningsRecord,
    ExemptionDecision,
    Finding,
    Member,
    MonthlyCompliance,
    ProofKitStatus,
    WalletResult,
)

_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


@dataclass(frozen=True, slots=True)
class IndexedFinding:
    """A finding paired with its stable position in the supplied sequence."""

    ordinal: int
    finding: Finding


@dataclass(frozen=True, slots=True)
class HighlightSpan:
    """A validated half-open interval into an unescaped clinical note."""

    start: int
    end: int
    source_ordinal: int


@dataclass(frozen=True, slots=True)
class MergedHighlightSpan:
    """A merged half-open interval into an unescaped clinical note."""

    start: int
    end: int


@dataclass(frozen=True, slots=True)
class NoteEvidencePlan:
    """Deterministic highlight and standalone evidence decisions for one note."""

    merged_spans: tuple[MergedHighlightSpan, ...]
    standalone_findings: tuple[IndexedFinding, ...]


def _escape_text(value: str) -> str:
    """Escape an untrusted value for insertion into an HTML text node."""
    return html.escape(value, quote=True)


def _format_money(value: Decimal) -> str:
    """Format an exact Decimal money value with grouping and two decimals."""
    return f"${value:,.2f}"


def _format_hours(value: Decimal) -> str:
    """Format an exact Decimal hours value with two decimals."""
    return f"{value:.2f}"


def _format_date(value: date) -> str:
    """Format a contract date in its canonical ISO representation."""
    return value.isoformat()


def _is_valid_span(note: ClinicalNote, finding: Finding) -> bool:
    """Return whether a finding identifies its exact original note slice."""
    start = finding.quote_start
    end = finding.quote_end
    return (
        finding.note_id == note.note_id
        and 0 <= start < end <= len(note.text)
        and note.text[start:end] == finding.quote
    )


def _merge_spans(spans: Sequence[HighlightSpan]) -> tuple[MergedHighlightSpan, ...]:
    """Merge an already sorted sequence of overlapping or adjacent spans."""
    if not spans:
        return ()

    current_start = spans[0].start
    current_end = spans[0].end
    merged: list[MergedHighlightSpan] = []

    for span in spans[1:]:
        if span.start <= current_end:
            current_end = max(current_end, span.end)
        else:
            merged.append(MergedHighlightSpan(start=current_start, end=current_end))
            current_start = span.start
            current_end = span.end

    merged.append(MergedHighlightSpan(start=current_start, end=current_end))
    return tuple(merged)


def _plan_note_evidence(
    note: ClinicalNote,
    indexed_findings: Sequence[IndexedFinding],
) -> NoteEvidencePlan:
    """Validate, sort, and merge findings that reference one note."""
    valid_spans: list[HighlightSpan] = []
    standalone_findings: list[IndexedFinding] = []

    for indexed_finding in indexed_findings:
        finding = indexed_finding.finding
        if finding.note_id != note.note_id:
            continue
        if _is_valid_span(note, finding):
            valid_spans.append(
                HighlightSpan(
                    start=finding.quote_start,
                    end=finding.quote_end,
                    source_ordinal=indexed_finding.ordinal,
                )
            )
        else:
            standalone_findings.append(indexed_finding)

    valid_spans.sort(key=lambda span: (span.start, span.end, span.source_ordinal))
    return NoteEvidencePlan(
        merged_spans=_merge_spans(valid_spans),
        standalone_findings=tuple(standalone_findings),
    )


def _find_missing_note_evidence(
    notes: Sequence[ClinicalNote],
    indexed_findings: Sequence[IndexedFinding],
) -> tuple[IndexedFinding, ...]:
    """Return unmatched findings in their original supplied order."""
    supplied_note_ids = {note.note_id for note in notes}
    return tuple(
        indexed_finding
        for indexed_finding in indexed_findings
        if indexed_finding.finding.note_id not in supplied_note_ids
    )


def _render_highlighted_text(
    text: str,
    spans: Sequence[MergedHighlightSpan],
) -> str:
    """Slice raw note text at planned offsets, then escape every text fragment."""
    parts: list[str] = []
    cursor = 0
    for span in spans:
        parts.extend(
            (
                _escape_text(text[cursor : span.start]),
                "<mark>",
                _escape_text(text[span.start : span.end]),
                "</mark>",
            )
        )
        cursor = span.end
    parts.append(_escape_text(text[cursor:]))
    return "".join(parts)


def _render_standalone_finding(
    finding: Finding,
    *,
    include_note_id: bool,
) -> str:
    """Render invalid or unmatched evidence without applying its offsets."""
    parts = ["<li>"]
    if include_note_id:
        parts.extend(
            (
                "<strong>Note ID:</strong> ",
                _escape_text(finding.note_id),
                " — ",
            )
        )
    parts.extend((_escape_text(finding.quote), "</li>\n"))
    return "".join(parts)


def _render_note(note: ClinicalNote, plan: NoteEvidencePlan) -> str:
    parts = [
        "<article><p>",
        _render_highlighted_text(note.text, plan.merged_spans),
        "</p></article>\n",
    ]
    if plan.standalone_findings:
        parts.extend(("<h3>Standalone evidence</h3>\n", "<ul>\n"))
        parts.extend(
            _render_standalone_finding(
                indexed_finding.finding,
                include_note_id=False,
            )
            for indexed_finding in plan.standalone_findings
        )
        parts.append("</ul>\n")
    return "".join(parts)


def _render_notes(
    notes: Sequence[ClinicalNote],
    indexed_findings: Sequence[IndexedFinding],
) -> str:
    if not notes:
        return ""

    parts = ["<section>\n<h2>Clinical notes</h2>\n"]
    for note in notes:
        parts.append(_render_note(note, _plan_note_evidence(note, indexed_findings)))
    parts.append("</section>\n")
    return "".join(parts)


def _render_missing_note_evidence(
    notes: Sequence[ClinicalNote],
    indexed_findings: Sequence[IndexedFinding],
) -> str:
    missing_findings = _find_missing_note_evidence(notes, indexed_findings)
    if not missing_findings:
        return ""

    parts = ["<section>\n<h2>Evidence for missing notes</h2>\n<ul>\n"]
    parts.extend(
        _render_standalone_finding(
            indexed_finding.finding,
            include_note_id=True,
        )
        for indexed_finding in missing_findings
    )
    parts.extend(("</ul>\n", "</section>\n"))
    return "".join(parts)


def _render_month_row(month: MonthlyCompliance) -> str:
    """Render one compliance month from exact Decimal source values."""
    review_reasons = "; ".join(_escape_text(reason) for reason in month.review_reasons)
    return "".join(
        (
            "<tr>",
            "<td>",
            _escape_text(month.month),
            "</td>",
            "<td>",
            _format_hours(month.total_hours),
            "</td>",
            "<td>",
            _format_money(month.total_income),
            "</td>",
            "<td>",
            "Yes" if month.qualifies else "No",
            "</td>",
            "<td>",
            _escape_text(month.basis.value),
            "</td>",
            "<td>",
            _format_hours(month.shortfall_hours),
            "</td>",
            "<td>",
            _format_money(month.shortfall_income),
            "</td>",
            "<td>",
            "Yes" if month.needs_review else "No",
            "</td>",
            "<td>",
            review_reasons,
            "</td>",
            "</tr>\n",
        )
    )


def _render_earnings_record(record: EarningsRecord) -> str:
    """Render untrusted wallet evidence as escaped visible text."""
    return "".join(
        (
            "<li><strong>Platform:</strong> ",
            _escape_text(record.platform),
            " <br><strong>Source quote:</strong> ",
            _escape_text(record.source_quote),
            "</li>\n",
        )
    )


def _render_wallet(wallet: WalletResult | None) -> str:
    """Render monthly compliance and ordered wallet evidence when supplied."""
    if wallet is None:
        return ""

    parts = [
        "<section>\n",
        "<h2>Monthly compliance</h2>\n",
        "<table>\n",
        "<thead><tr>",
        "<th>Month</th>",
        "<th>Hours</th>",
        "<th>Income</th>",
        "<th>Qualifies</th>",
        "<th>Basis</th>",
        "<th>Shortfall hours</th>",
        "<th>Shortfall income</th>",
        "<th>Needs review</th>",
        "<th>Review reasons</th>",
        "</tr></thead>\n",
        "<tbody>\n",
    ]
    parts.extend(_render_month_row(month) for month in wallet.months)
    parts.extend(("</tbody>\n", "</table>\n", "</section>\n"))

    if wallet.records:
        parts.extend(("<section>\n", "<h2>Wallet evidence</h2>\n", "<ul>\n"))
        parts.extend(_render_earnings_record(record) for record in wallet.records)
        parts.extend(("</ul>\n", "</section>\n"))

    return "".join(parts)


_STATUS_LABELS = {
    "protected": "Protected",
    "at_risk": "At risk",
    "needs_review": "Needs review",
}


def _status_label(value: str) -> str:
    """Return the fixed display label for an overall status value."""
    return _STATUS_LABELS[value]


def _render_member_identity(member: Member) -> str:
    """Render only the two member identifiers approved for packet sharing."""
    return "".join(
        (
            "<section>\n",
            "<h2>Member identity</h2>\n",
            "<p><strong>Display name:</strong> ",
            _escape_text(member.display_name),
            "</p>\n",
            "<p><strong>Member ID:</strong> ",
            _escape_text(member.member_id),
            "</p>\n",
            "</section>\n",
        )
    )


def _render_status(status: ProofKitStatus) -> str:
    """Render the fixed overall-status label and optional protection basis."""
    parts = [
        "<section>\n",
        "<h2>Overall status</h2>\n",
        "<p><strong>Status:</strong> ",
        _status_label(status.status),
        "</p>\n",
    ]
    if status.protected_by is not None:
        parts.extend(
            (
                "<p><strong>Protected by:</strong> ",
                _escape_text(status.protected_by),
                "</p>\n",
            )
        )
    parts.append("</section>\n")
    return "".join(parts)


def _render_exemption(exemption: ExemptionDecision | None) -> str:
    """Render an optional clinician statement and ordered review reasons."""
    if exemption is None:
        return ""

    parts = ["<section>\n", "<h2>Clinician statement</h2>\n"]
    if exemption.statement_draft is not None:
        parts.extend(
            (
                "<p><strong>Statement draft:</strong> ",
                _escape_text(exemption.statement_draft),
                "</p>\n",
            )
        )
    if exemption.review_reasons:
        parts.extend(("<h3>Review reasons</h3>\n", "<ul>\n"))
        parts.extend(
            "".join(("<li>", _escape_text(reason), "</li>\n"))
            for reason in exemption.review_reasons
        )
        parts.append("</ul>\n")
    parts.append("</section>\n")
    return "".join(parts)


def _render_deadlines_and_actions(status: ProofKitStatus) -> str:
    """Render all supplied dates and action items in their contract order."""
    parts = ["<section>\n", "<h2>Deadlines and actions</h2>\n"]
    if status.next_deadline is not None:
        parts.extend(
            (
                "<p><strong>Next deadline:</strong> ",
                _format_date(status.next_deadline),
                "</p>\n",
            )
        )
    if status.wallet is not None:
        parts.extend(
            (
                "<p><strong>Proof due date:</strong> ",
                _format_date(status.wallet.proof_due_date),
                "</p>\n",
                "<p><strong>Next renewal date:</strong> ",
                _format_date(status.wallet.next_renewal_date),
                "</p>\n",
            )
        )
    if status.action_items:
        parts.extend(("<h3>Action items</h3>\n", "<ul>\n"))
        for action in status.action_items:
            parts.extend(
                (
                    "<li><strong>Title:</strong> ",
                    _escape_text(action.title),
                    " <br><strong>Detail:</strong> ",
                    _escape_text(action.detail),
                )
            )
            if action.due is not None:
                parts.extend(
                    (
                        " <br><strong>Due:</strong> ",
                        _format_date(action.due),
                    )
                )
            parts.append("</li>\n")
        parts.append("</ul>\n")
    parts.append("</section>\n")
    return "".join(parts)


def _render_disclaimer(disclaimer: str) -> str:
    """Render the required disclaimer through the untrusted-text boundary."""
    return "".join(
        (
            "<section>\n",
            "<h2>Disclaimer</h2>\n",
            "<p>",
            _escape_text(disclaimer),
            "</p>\n",
            "</section>\n",
        )
    )


def render_packet(
    member: Member,
    status: ProofKitStatus,
    findings: Sequence[Finding] | None = None,
    notes: Sequence[ClinicalNote] = (),
) -> str:
    """Render one safe, self-contained HTML Proof Packet document."""
    normalized_findings = () if findings is None else tuple(findings)
    indexed_findings = tuple(
        IndexedFinding(ordinal=ordinal, finding=finding)
        for ordinal, finding in enumerate(normalized_findings)
    )

    parts = [
        "<!doctype html>\n",
        '<html lang="en">\n',
        "<head>\n",
        '<meta charset="utf-8">\n',
        f'<meta http-equiv="Content-Security-Policy" content="{_CSP}">\n',
        "<title>Proof Packet</title>\n",
        "<style>\n",
        "body { font-family: Arial, sans-serif; margin: 2rem; color: #1f2937; }\n",
        "main { max-width: 60rem; margin: 0 auto; }\n",
        "section { margin-block: 1.5rem; }\n",
        "article, li { overflow-wrap: anywhere; }\n",
        "</style>\n",
        "</head>\n",
        "<body>\n",
        "<main>\n",
        "<h1>Proof Packet</h1>\n",
        _render_member_identity(member),
        _render_status(status),
        _render_wallet(status.wallet),
        _render_notes(notes, indexed_findings),
        _render_missing_note_evidence(notes, indexed_findings),
        _render_exemption(status.exemption),
        _render_deadlines_and_actions(status),
        _render_disclaimer(status.disclaimer),
        "</main>\n",
        "</body>\n",
        "</html>\n",
    ]
    return "".join(parts)
