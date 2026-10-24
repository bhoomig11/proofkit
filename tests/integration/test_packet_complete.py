"""Complete integration examples for deterministic Proof Packet assembly."""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from html import escape
from html.parser import HTMLParser

from proofkit.contracts import (
    ActionItem,
    ClinicalNote,
    ComplianceBasis,
    DecisionOutcome,
    EarningsRecord,
    ExemptionDecision,
    ExemptionType,
    Finding,
    FindingStatus,
    MatchedRule,
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration.proof_packet import render_packet


MEMBER_ID = "SYN-4242"
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
COMPLETE_SECTION_ORDER = [
    "Member identity",
    "Overall status",
    "Monthly compliance",
    "Wallet evidence",
    "Clinical notes",
    "Evidence for missing notes",
    "Clinician statement",
    "Deadlines and actions",
    "Disclaimer",
]


class CompletePacketParser(HTMLParser):
    """Collect document structure and decoded integration-level content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.declarations: list[str] = []
        self.start_tags: Counter[str] = Counter()
        self.end_tags: Counter[str] = Counter()
        self.attributes: dict[str, list[dict[str, str | None]]] = {}
        self.headings: list[str] = []
        self.mark_texts: list[str] = []
        self.text_parts: list[str] = []
        self.tbody_count = 0
        self.tbody_rows = 0
        self._heading_parts: list[str] | None = None
        self._mark_parts: list[str] | None = None
        self._in_tbody = False

    @staticmethod
    def _normalized(parts: list[str]) -> str:
        return " ".join("".join(parts).split())

    @property
    def visible_text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())

    def handle_decl(self, decl: str) -> None:
        self.declarations.append(decl.lower())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self.start_tags[tag] += 1
        self.attributes.setdefault(tag, []).append(
            {name.lower(): value for name, value in attrs}
        )
        if tag == "h2":
            self._heading_parts = []
        elif tag == "mark":
            assert self._mark_parts is None
            self._mark_parts = []
        elif tag == "tbody":
            self.tbody_count += 1
            self._in_tbody = True
        elif tag == "tr" and self._in_tbody:
            self.tbody_rows += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        self.end_tags[tag] += 1
        if tag == "h2" and self._heading_parts is not None:
            self.headings.append(self._normalized(self._heading_parts))
            self._heading_parts = None
        elif tag == "mark" and self._mark_parts is not None:
            self.mark_texts.append("".join(self._mark_parts))
            self._mark_parts = None
        elif tag == "tbody":
            self._in_tbody = False

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text_parts.append(data.strip())
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._mark_parts is not None:
            self._mark_parts.append(data)


def _parse(document: str) -> CompletePacketParser:
    parser = CompletePacketParser()
    parser.feed(document)
    parser.close()
    return parser


def _assert_one_complete_document(document: str, parser: CompletePacketParser) -> None:
    assert document.startswith("<!doctype html>\n")
    assert document.endswith("</html>\n")
    assert "\r" not in document
    assert parser.declarations == ["doctype html"]
    for tag in ("html", "head", "body", "main"):
        assert parser.start_tags[tag] == 1
        assert parser.end_tags[tag] == 1
    assert parser.start_tags["style"] == 1
    assert parser.end_tags["style"] == 1
    assert parser.start_tags["script"] == 0
    assert parser.start_tags["link"] == 0

    csp_values = [
        attrs.get("content")
        for attrs in parser.attributes.get("meta", [])
        if attrs.get("http-equiv") == "Content-Security-Policy"
    ]
    assert csp_values == [CSP]
    for attributes in parser.attributes.values():
        for attrs in attributes:
            assert not {"href", "src", "action"}.intersection(attrs)


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name='Complete <Member> & "Reviewer"',
        eligibility_group="PRIVATE-GROUP-SENTINEL",
        renewal_date=date(2035, 5, 6),
        phone_last4="8642",
    )


def _finding(
    note: ClinicalNote,
    *,
    finding_id: str,
    quote: str,
) -> Finding:
    start = note.text.index(quote)
    return Finding(
        finding_id=finding_id,
        note_id=note.note_id,
        note_date=note.note_date,
        condition="Representative condition",
        icd10="M32.9",
        status=FindingStatus.CURRENT,
        quote=quote,
        quote_start=start,
        quote_end=start + len(quote),
        confidence=0.98,
    )


def _record(
    *,
    record_id: str,
    platform: str,
    source_quote: str,
    period_start: date,
) -> EarningsRecord:
    return EarningsRecord(
        record_id=record_id,
        member_id=MEMBER_ID,
        source_doc_id=f"document-{record_id}",
        platform=platform,
        period_start=period_start,
        period_end=period_start,
        hours=Decimal("41.25"),
        gross_income=Decimal("812.34"),
        source_quote=source_quote,
        confidence=0.97,
    )


def _complete_packet_inputs() -> tuple[
    Member,
    ProofKitStatus,
    list[Finding],
    list[ClinicalNote],
]:
    first_note = ClinicalNote(
        note_id="note-zeta",
        member_id=MEMBER_ID,
        note_date=date(2026, 2, 1),
        author_role="specialist",
        text="NOTE-ZETA: persistent fatigue & pain limits shifts.",
    )
    second_note = ClinicalNote(
        note_id="note-alpha",
        member_id=MEMBER_ID,
        note_date=date(2026, 1, 1),
        author_role="clinician",
        text="NOTE-ALPHA: severe <mobility> limits remain.",
    )
    first_finding = _finding(
        first_note,
        finding_id="finding-zeta",
        quote="fatigue & pain",
    )
    second_finding = _finding(
        second_note,
        finding_id="finding-alpha",
        quote="<mobility>",
    )
    missing_finding = Finding(
        finding_id="finding-missing",
        note_id="note-missing",
        note_date=date(2026, 2, 2),
        condition="Missing-note condition",
        icd10="F32.9",
        status=FindingStatus.CURRENT,
        quote="MISSING-QUOTE <must stay visible>",
        quote_start=0,
        quote_end=len("MISSING-QUOTE <must stay visible>"),
        confidence=0.88,
    )

    records = [
        _record(
            record_id="record-zeta",
            platform="platform-zeta & work",
            source_quote="RECORD-ZETA <gross> $812.34",
            period_start=date(2026, 2, 2),
        ),
        _record(
            record_id="record-alpha",
            platform="platform-alpha",
            source_quote="RECORD-ALPHA 'hours' 41.25",
            period_start=date(2026, 1, 2),
        ),
    ]
    months = [
        MonthlyCompliance(
            month="2026-02",
            total_hours=Decimal("39.50"),
            hours_known_for_all_records=False,
            total_income=Decimal("812.34"),
            qualifies=False,
            basis=ComplianceBasis.NONE,
            shortfall_hours=Decimal("40.50"),
            shortfall_income=Decimal("667.66"),
            record_ids=["record-zeta"],
            needs_review=True,
            review_reasons=["MONTH-REVIEW <hours unavailable>"],
        ),
        MonthlyCompliance(
            month="2026-01",
            total_hours=Decimal("82.75"),
            hours_known_for_all_records=True,
            total_income=Decimal("1.50"),
            qualifies=True,
            basis=ComplianceBasis.HOURS,
            shortfall_hours=Decimal("0"),
            shortfall_income=Decimal("0"),
            record_ids=["record-alpha"],
        ),
    ]
    wallet = WalletResult(
        member_id=MEMBER_ID,
        records=records,
        months=months,
        verification_months=["2026-02", "2026-01"],
        next_renewal_date=date(2026, 4, 13),
        proof_due_date=date(2026, 3, 12),
        rules_version="wallet-complete-v1",
    )
    exemption = ExemptionDecision(
        member_id=MEMBER_ID,
        outcome=DecisionOutcome.EXEMPT,
        exemption_type=ExemptionType.MEDICALLY_FRAIL,
        confidence=0.93,
        matched_rules=[
            MatchedRule(
                rule_id="complete-rule",
                category="serious_complex_medical",
                finding_ids=[first_finding.finding_id],
                rationale="Contract-only rationale",
            )
        ],
        evidence_finding_ids=[first_finding.finding_id, second_finding.finding_id],
        lookback_months=12,
        as_of=date(2026, 3, 1),
        rules_version="reasoning-complete-v1",
        review_reasons=[
            "EXEMPTION-REVIEW <confirm signature>",
            "EXEMPTION-REVIEW-SECOND & retain order",
        ],
        statement_draft="STATEMENT-DRAFT <clinician> & member evidence.",
    )
    status = ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.PROTECTED,
        protected_by="exemption:<medically_frail>",
        exemption=exemption,
        wallet=wallet,
        next_deadline=date(2026, 3, 11),
        action_items=[
            ActionItem(
                priority=5,
                title="ACTION-ZETA <upload>",
                detail="DETAIL-ZETA & preserve first",
                due=date(2026, 3, 14),
            ),
            ActionItem(
                priority=1,
                title="ACTION-ALPHA",
                detail="DETAIL-ALPHA remains second",
            ),
        ],
        disclaimer="DISCLAIMER-COMPLETE <MassHealth decides> & verify.",
    )
    # Deliberately use non-alphabetic/non-chronological sequences to pin traversal order.
    findings = [second_finding, missing_finding, first_finding]
    notes = [first_note, second_note]
    return _member(), status, findings, notes


def test_complete_packet_has_fixed_section_order_and_all_content_once() -> None:
    """Validates: Requirements 1.1, 1.2 and 1.3."""
    member, status, findings, notes = _complete_packet_inputs()

    document = render_packet(member, status, findings=findings, notes=notes)
    parser = _parse(document)

    _assert_one_complete_document(document, parser)
    assert parser.headings == COMPLETE_SECTION_ORDER
    assert parser.mark_texts == ["fatigue & pain", "<mobility>"]

    required_visible_values = [
        member.display_name,
        member.member_id,
        "Protected",
        status.protected_by,
        "2026-02",
        "39.50",
        "$812.34",
        "40.50",
        "$667.66",
        "2026-01",
        "82.75",
        "$1.50",
        "platform-zeta & work",
        "RECORD-ZETA <gross> $812.34",
        "platform-alpha",
        "RECORD-ALPHA 'hours' 41.25",
        "NOTE-ZETA:",
        "fatigue & pain",
        "NOTE-ALPHA:",
        "<mobility>",
        "note-missing",
        "MISSING-QUOTE <must stay visible>",
        status.exemption.statement_draft,
        *status.exemption.review_reasons,
        status.next_deadline.isoformat(),
        status.wallet.proof_due_date.isoformat(),
        status.wallet.next_renewal_date.isoformat(),
        status.action_items[0].title,
        status.action_items[0].detail,
        status.action_items[0].due.isoformat(),
        status.action_items[1].title,
        status.action_items[1].detail,
        status.disclaimer,
    ]
    assert all(value in parser.visible_text for value in required_visible_values)

    ordered_groups = [
        [month.month for month in status.wallet.months],
        [record.platform for record in status.wallet.records],
        ["NOTE-ZETA:", "NOTE-ALPHA:"],
        list(status.exemption.review_reasons),
        [action.title for action in status.action_items],
    ]
    for values in ordered_groups:
        escaped_values = [escape(value, quote=True) for value in values]
        assert [document.index(value) for value in escaped_values] == sorted(
            document.index(value) for value in escaped_values
        )

    missing_finding = next(
        finding for finding in findings if finding.note_id == "note-missing"
    )
    canonical_values = [
        member.display_name,
        member.member_id,
        status.protected_by,
        "MONTH-REVIEW <hours unavailable>",
        *(record.platform for record in status.wallet.records),
        *(record.source_quote for record in status.wallet.records),
        "fatigue & pain",
        "<mobility>",
        missing_finding.quote,
        missing_finding.note_id,
        status.exemption.statement_draft,
        *status.exemption.review_reasons,
        *(action.title for action in status.action_items),
        *(action.detail for action in status.action_items),
        status.disclaimer,
    ]
    assert all(document.count(escape(value, quote=True)) == 1 for value in canonical_values)
    canonical_labels = [
        "Display name:",
        "Member ID:",
        "Status:",
        "Protected by:",
        "Statement draft:",
        "Next deadline:",
        "Proof due date:",
        "Next renewal date:",
    ]
    assert all(document.count(label) == 1 for label in canonical_labels)
    canonical_dates = [
        status.next_deadline,
        status.wallet.proof_due_date,
        status.wallet.next_renewal_date,
        status.action_items[0].due,
    ]
    assert all(document.count(value.isoformat()) == 1 for value in canonical_dates)


def test_default_arguments_allow_optional_sections_to_be_omitted() -> None:
    """Validates: Requirements 1.4, 4.3 and 8.6."""
    status = ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.NEEDS_REVIEW,
        disclaimer="DEFAULT-ARGUMENT-DISCLAIMER",
    )

    document = render_packet(_member(), status)
    parser = _parse(document)

    _assert_one_complete_document(document, parser)
    assert parser.headings == [
        "Member identity",
        "Overall status",
        "Deadlines and actions",
        "Disclaimer",
    ]
    assert parser.tbody_count == 0
    assert parser.tbody_rows == 0
    assert "Clinical notes" not in parser.headings
    assert "Evidence for missing notes" not in parser.headings
    assert "Monthly compliance" not in parser.headings
    assert "Wallet evidence" not in parser.headings
    assert "Clinician statement" not in parser.headings


def test_empty_wallet_months_render_an_empty_monthly_table() -> None:
    """Validates: Requirement 8.7."""
    wallet = WalletResult(
        member_id=MEMBER_ID,
        records=[],
        months=[],
        verification_months=[],
        next_renewal_date=date(2027, 8, 9),
        proof_due_date=date(2027, 7, 8),
        rules_version="empty-wallet-v1",
    )
    status = ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.AT_RISK,
        wallet=wallet,
        disclaimer="EMPTY-WALLET-DISCLAIMER",
    )

    document = render_packet(_member(), status)
    parser = _parse(document)

    _assert_one_complete_document(document, parser)
    assert parser.headings == [
        "Member identity",
        "Overall status",
        "Monthly compliance",
        "Deadlines and actions",
        "Disclaimer",
    ]
    assert parser.start_tags["table"] == 1
    assert parser.tbody_count == 1
    assert parser.tbody_rows == 0


def test_complete_packet_is_string_and_utf8_byte_deterministic() -> None:
    """Validates: Requirements 11.1, 11.2, 11.3, 11.4 and 12.9."""
    member, status, findings, notes = _complete_packet_inputs()

    first = render_packet(member, status, findings=findings, notes=notes)
    second = render_packet(member, status, findings=findings, notes=notes)

    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")
