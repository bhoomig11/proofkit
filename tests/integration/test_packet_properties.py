"""Focused property tests for the public Proof Packet renderer boundary."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import escape, unescape
from html.parser import HTMLParser

from hypothesis import given, settings, strategies as st

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
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration.packet import render_packet


MEMBER_ID = "SYN-0001"
CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
Span = tuple[int, int]
PacketInputs = tuple[
    Member,
    ProofKitStatus,
    tuple[Finding, ...],
    tuple[ClinicalNote, ...],
]
URL_ATTRIBUTES = {
    "action",
    "background",
    "cite",
    "data",
    "formaction",
    "href",
    "manifest",
    "ping",
    "poster",
    "src",
    "srcset",
    "xlink:href",
}
ADVERSARIAL_FRAGMENTS = (
    "<ScRiPt src=//evil.test/x>x</ScRiPt>",
    '\"><img src=//evil.test/p onerror=x>',
    "</style><link href=https://evil.test/x>",
    "<a href=JaVaScRiPt:x onclick=x>x</a>",
    "<iframe srcdoc='<script>x</script>'>",
    "&lt;ScRiPt&gt;x&lt;/ScRiPt&gt;",
    "javascript:https://evil.test/",
    '" onload=x data-value="',
    "url(https://evil.test/font.woff2)",
    "' & < > \" / =",
)
TEXT_CHARACTERS = st.characters(blacklist_categories=("Cs",))
SHORT_TEXT = st.text(alphabet=TEXT_CHARACTERS, min_size=1, max_size=40)
ADVERSARIAL_TEXT = st.one_of(
    st.sampled_from(ADVERSARIAL_FRAGMENTS),
    SHORT_TEXT,
    st.tuples(
        st.sampled_from(ADVERSARIAL_FRAGMENTS),
        st.text(alphabet=TEXT_CHARACTERS, max_size=8),
    ).map(lambda pieces: "".join(pieces)),
)
NOTE_TEXT = st.one_of(
    ADVERSARIAL_TEXT,
    st.text(alphabet=TEXT_CHARACTERS, min_size=1, max_size=80),
)
OPTIONAL_DATE = st.one_of(
    st.none(),
    st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31)),
)


class PacketHTMLOracle(HTMLParser):
    """Collect decoded marks and authored capabilities from rendered HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, tuple[tuple[str, str | None], ...]]] = []
        self.mark_texts: list[str] = []
        self.nested_mark_count = 0
        self.style_blocks: list[str] = []
        self._mark_chunks: list[list[str]] = []
        self._style_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        normalized_attrs = tuple((name.lower(), value) for name, value in attrs)
        self.elements.append((normalized_tag, normalized_attrs))
        if normalized_tag == "mark":
            if self._mark_chunks:
                self.nested_mark_count += 1
            self._mark_chunks.append([])
        elif normalized_tag == "style":
            self._style_chunks = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "mark" and self._mark_chunks:
            self.mark_texts.append("".join(self._mark_chunks.pop()))
        elif normalized_tag == "style" and self._style_chunks is not None:
            self.style_blocks.append("".join(self._style_chunks))
            self._style_chunks = None

    def handle_data(self, data: str) -> None:
        if self._style_chunks is not None:
            self._style_chunks.append(data)
        for chunks in self._mark_chunks:
            chunks.append(data)

    @property
    def csp_values(self) -> list[str | None]:
        return [
            dict(attrs).get("content")
            for tag, attrs in self.elements
            if tag == "meta"
            and (dict(attrs).get("http-equiv") or "").lower()
            == "content-security-policy"
        ]


def _parse(document: str) -> PacketHTMLOracle:
    parser = PacketHTMLOracle()
    parser.feed(document)
    parser.close()
    return parser


def _member(display_name: str = "Property Test Member") -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name=display_name,
        renewal_date=date(2026, 12, 31),
    )


def _status(**changes: object) -> ProofKitStatus:
    values: dict[str, object] = {
        "member_id": MEMBER_ID,
        "status": OverallStatus.NEEDS_REVIEW,
        "disclaimer": "Property test disclaimer",
    }
    values.update(changes)
    return ProofKitStatus(**values)


def _finding(
    note: ClinicalNote,
    start: int,
    end: int,
    ordinal: int,
) -> Finding:
    return Finding(
        finding_id=f"finding-{ordinal}",
        note_id=note.note_id,
        note_date=note.note_date,
        condition="Property condition",
        icd10="M32.9",
        status=FindingStatus.CURRENT,
        quote=note.text[start:end],
        quote_start=start,
        quote_end=end,
        confidence=Decimal("0.99"),
    )


def _merge_intervals_independently(spans: list[Span]) -> list[Span]:
    """Compute the interval union without calling renderer implementation helpers."""
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

    current_start, current_end = ordered[0][1]
    merged: list[Span] = []
    for _, (next_start, next_end) in ordered[1:]:
        if next_start <= current_end:
            current_end = max(current_end, next_end)
        else:
            merged.append((current_start, current_end))
            current_start, current_end = next_start, next_end
    merged.append((current_start, current_end))
    return merged


@st.composite
def capability_inputs(draw: st.DrawFn) -> PacketInputs:
    payloads = [draw(ADVERSARIAL_TEXT) for _ in range(8)]
    note_text = f"{payloads[0]}\n{payloads[1]}"
    quote_start = len(payloads[0]) + 1
    note = ClinicalNote(
        note_id="capability-note",
        member_id=MEMBER_ID,
        note_date=date(2026, 1, 2),
        text=note_text,
    )
    finding = Finding(
        finding_id="capability-finding",
        note_id=note.note_id,
        note_date=note.note_date,
        condition="Capability condition",
        icd10="M32.9",
        status=FindingStatus.CURRENT,
        quote=payloads[1],
        quote_start=quote_start,
        quote_end=quote_start + len(payloads[1]),
        confidence=Decimal("0.98"),
    )
    record = EarningsRecord(
        record_id="capability-record",
        member_id=MEMBER_ID,
        source_doc_id="capability-document",
        platform=payloads[3],
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 7),
        hours=Decimal("12.50"),
        gross_income=Decimal("250.00"),
        source_quote=payloads[4],
        confidence=Decimal("0.97"),
    )
    wallet = WalletResult(
        member_id=MEMBER_ID,
        records=[record],
        months=[],
        verification_months=["2026-01"],
        next_renewal_date=date(2026, 12, 31),
        proof_due_date=date(2026, 2, 15),
        rules_version="property-v1",
    )
    status = _status(
        protected_by=payloads[5],
        wallet=wallet,
        action_items=[
            ActionItem(
                priority=1,
                title=payloads[6],
                detail=payloads[7],
            )
        ],
        disclaimer=payloads[2],
    )
    return _member(payloads[2]), status, (finding,), (note,)


@st.composite
def note_and_spans(draw: st.DrawFn) -> tuple[ClinicalNote, list[Span]]:
    text = draw(NOTE_TEXT)
    text_length = len(text)
    base_start = draw(st.integers(min_value=0, max_value=text_length - 1))
    base_end = draw(st.integers(min_value=base_start + 1, max_value=text_length))
    spans: list[Span] = [(base_start, base_end)]

    relations = ["random", "duplicate"]
    if text_length >= 2:
        relations.append("adjacent")
    if text_length >= 3:
        relations.extend(("overlapping", "nested", "disjoint"))
    relation = draw(st.sampled_from(relations))
    if relation == "duplicate":
        spans.extend(((base_start, base_end), (base_start, base_end)))
    elif relation == "adjacent":
        spans.extend(((0, 1), (1, text_length)))
    elif relation == "overlapping":
        spans.extend(((0, text_length - 1), (1, text_length)))
    elif relation == "nested":
        spans.extend(((0, text_length), (1, text_length - 1)))
    elif relation == "disjoint":
        spans.extend(((0, 1), (2, text_length)))

    for _ in range(draw(st.integers(min_value=0, max_value=6))):
        start = draw(st.integers(min_value=0, max_value=text_length - 1))
        end = draw(st.integers(min_value=start + 1, max_value=text_length))
        spans.append((start, end))

    shuffled = draw(st.permutations(spans))
    note = ClinicalNote(
        note_id="highlight-note",
        member_id=MEMBER_ID,
        note_date=date(2026, 2, 3),
        text=text,
    )
    return note, list(shuffled)


@st.composite
def missing_note_inputs(draw: st.DrawFn) -> PacketInputs:
    quote = draw(ADVERSARIAL_TEXT)
    note_id_suffix = draw(st.text(alphabet=TEXT_CHARACTERS, max_size=30))
    missing_note_id = f"missing<{note_id_suffix}>"
    present_note = ClinicalNote(
        note_id="present-note",
        member_id=MEMBER_ID,
        note_date=date(2026, 3, 4),
        text=draw(NOTE_TEXT),
    )
    finding = Finding(
        finding_id="missing-finding",
        note_id=missing_note_id,
        note_date=date(2026, 3, 5),
        condition="Missing note condition",
        icd10="F32.9",
        status=FindingStatus.CURRENT,
        quote=quote,
        quote_start=0,
        quote_end=len(quote),
        confidence=Decimal("0.91"),
    )
    return _member(), _status(), (finding,), (present_note,)


@st.composite
def deterministic_packet_inputs(draw: st.DrawFn) -> PacketInputs:
    member = Member(
        member_id=MEMBER_ID,
        display_name=draw(ADVERSARIAL_TEXT),
        renewal_date=draw(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2040, 12, 31))
        ),
    )

    notes: list[ClinicalNote] = []
    findings: list[Finding] = []
    if draw(st.booleans()):
        note = ClinicalNote(
            note_id="deterministic-note",
            member_id=MEMBER_ID,
            note_date=date(2026, 4, 5),
            text=draw(NOTE_TEXT),
        )
        notes.append(note)
        if draw(st.booleans()):
            start = draw(st.integers(min_value=0, max_value=len(note.text) - 1))
            end = draw(st.integers(min_value=start + 1, max_value=len(note.text)))
            findings.append(_finding(note, start, end, 0))

    if draw(st.booleans()):
        missing_quote = draw(ADVERSARIAL_TEXT)
        findings.append(
            Finding(
                finding_id="deterministic-missing",
                note_id="absent<note>",
                note_date=date(2026, 4, 6),
                condition="Missing condition",
                icd10="F32.9",
                status=FindingStatus.CURRENT,
                quote=missing_quote,
                quote_start=0,
                quote_end=len(missing_quote),
                confidence=Decimal("0.90"),
            )
        )
    if draw(st.booleans()):
        findings.reverse()

    wallet: WalletResult | None = None
    if draw(st.booleans()):
        records: list[EarningsRecord] = []
        if draw(st.booleans()):
            record_hours = (
                Decimal(draw(st.integers(min_value=0, max_value=74_400)))
                / Decimal("100")
            )
            record_income = (
                Decimal(draw(st.integers(min_value=0, max_value=10_000_000)))
                / Decimal("100")
            )
            records.append(
                EarningsRecord(
                    record_id="deterministic-record",
                    member_id=MEMBER_ID,
                    source_doc_id="deterministic-document",
                    platform=draw(ADVERSARIAL_TEXT),
                    period_start=date(2026, 1, 1),
                    period_end=date(2026, 1, 7),
                    hours=record_hours,
                    gross_income=record_income,
                    source_quote=draw(ADVERSARIAL_TEXT),
                    confidence=Decimal("0.95"),
                )
            )

        months: list[MonthlyCompliance] = []
        if draw(st.booleans()):
            qualifies = draw(st.booleans())
            basis = (
                draw(
                    st.sampled_from(
                        (
                            ComplianceBasis.HOURS,
                            ComplianceBasis.INCOME,
                            ComplianceBasis.AVERAGED_INCOME,
                        )
                    )
                )
                if qualifies
                else ComplianceBasis.NONE
            )
            months.append(
                MonthlyCompliance(
                    month=f"2026-{draw(st.integers(min_value=1, max_value=12)):02d}",
                    total_hours=Decimal(
                        draw(st.integers(min_value=0, max_value=74_400))
                    )
                    / Decimal("100"),
                    hours_known_for_all_records=draw(st.booleans()),
                    total_income=Decimal(
                        draw(st.integers(min_value=0, max_value=10_000_000))
                    )
                    / Decimal("100"),
                    qualifies=qualifies,
                    basis=basis,
                    shortfall_hours=Decimal(
                        draw(st.integers(min_value=0, max_value=74_400))
                    )
                    / Decimal("100"),
                    shortfall_income=Decimal(
                        draw(st.integers(min_value=0, max_value=10_000_000))
                    )
                    / Decimal("100"),
                    record_ids=[record.record_id for record in records],
                    needs_review=draw(st.booleans()),
                    review_reasons=draw(
                        st.lists(ADVERSARIAL_TEXT, min_size=0, max_size=2)
                    ),
                )
            )
        wallet = WalletResult(
            member_id=MEMBER_ID,
            records=records,
            months=months,
            verification_months=[month.month for month in months],
            next_renewal_date=draw(
                st.dates(
                    min_value=date(2020, 1, 1),
                    max_value=date(2040, 12, 31),
                )
            ),
            proof_due_date=draw(
                st.dates(
                    min_value=date(2020, 1, 1),
                    max_value=date(2040, 12, 31),
                )
            ),
            rules_version="deterministic-wallet-v1",
        )

    exemption: ExemptionDecision | None = None
    if draw(st.booleans()):
        exemption = ExemptionDecision(
            member_id=MEMBER_ID,
            outcome=DecisionOutcome.NOT_EXEMPT,
            exemption_type=ExemptionType.NONE,
            confidence=Decimal("0.80"),
            matched_rules=[],
            evidence_finding_ids=[],
            lookback_months=draw(st.integers(min_value=1, max_value=60)),
            as_of=date(2026, 5, 6),
            rules_version="deterministic-reasoning-v1",
            review_reasons=draw(
                st.lists(ADVERSARIAL_TEXT, min_size=0, max_size=2)
            ),
            statement_draft=draw(st.one_of(st.none(), ADVERSARIAL_TEXT)),
        )

    actions = [
        ActionItem(
            priority=draw(st.integers(min_value=1, max_value=5)),
            title=draw(ADVERSARIAL_TEXT),
            detail=draw(ADVERSARIAL_TEXT),
            due=draw(OPTIONAL_DATE),
        )
        for _ in range(draw(st.integers(min_value=0, max_value=2)))
    ]
    status = ProofKitStatus(
        member_id=MEMBER_ID,
        status=draw(st.sampled_from(tuple(OverallStatus))),
        protected_by=draw(st.one_of(st.none(), ADVERSARIAL_TEXT)),
        exemption=exemption,
        wallet=wallet,
        next_deadline=draw(OPTIONAL_DATE),
        action_items=actions,
        disclaimer=draw(st.one_of(st.just(""), ADVERSARIAL_TEXT)),
    )
    return member, status, tuple(findings), tuple(notes)


@given(inputs=capability_inputs())
@settings(max_examples=100)
def test_property_3_capability_confinement_under_arbitrary_input(
    inputs: PacketInputs,
) -> None:
    # Feature: proof-packet, Property 3: Capability confinement under arbitrary input
    member, status, findings, notes = inputs
    document = render_packet(member, status, findings=findings, notes=notes)
    parser = _parse(document)

    tags = [tag for tag, _ in parser.elements]
    assert "script" not in tags
    assert parser.csp_values == [CSP]
    assert "link" not in tags
    assert len(parser.style_blocks) == 1
    assert "@import" not in parser.style_blocks[0].lower()
    assert "url(" not in parser.style_blocks[0].lower()

    for tag, attrs in parser.elements:
        attribute_map = dict(attrs)
        assert (attribute_map.get("http-equiv") or "").lower() != "refresh"
        for name, value in attrs:
            assert not name.startswith("on")
            if value is None:
                continue
            compact_value = "".join(unescape(value).split()).lower()
            assert "javascript:" not in compact_value
            if name in URL_ATTRIBUTES:
                assert compact_value.startswith(("data:", "#")), (tag, name, value)
                assert "http:" not in compact_value
                assert "https:" not in compact_value
                assert "//" not in compact_value


@given(note_with_spans=note_and_spans())
@settings(max_examples=100)
def test_property_5_merged_highlights_exactly_cover_valid_evidence(
    note_with_spans: tuple[ClinicalNote, list[Span]],
) -> None:
    # Feature: proof-packet, Property 5: Merged highlights exactly cover valid evidence
    note, source_spans = note_with_spans
    expected_spans = _merge_intervals_independently(source_spans)
    findings = [
        _finding(note, start, end, ordinal)
        for ordinal, (start, end) in enumerate(source_spans)
    ]

    document = render_packet(
        _member(),
        _status(),
        findings=findings,
        notes=[note],
    )
    parser = _parse(document)

    expected_mark_texts = [note.text[start:end] for start, end in expected_spans]
    assert parser.nested_mark_count == 0
    assert parser.mark_texts == expected_mark_texts
    assert len(parser.mark_texts) == len(expected_spans)
    assert all(
        left_end < right_start
        for (_, left_end), (right_start, _) in zip(expected_spans, expected_spans[1:])
    )
    for mark_text, (start, end) in zip(parser.mark_texts, expected_spans):
        assert mark_text == note.text[start:end]
    for source_start, source_end in source_spans:
        containing_spans = [
            (merged_start, merged_end)
            for merged_start, merged_end in expected_spans
            if merged_start <= source_start and source_end <= merged_end
        ]
        assert len(containing_spans) == 1


@given(inputs=missing_note_inputs())
@settings(max_examples=100)
def test_property_7_missing_note_evidence_is_preserved_and_labelled(
    inputs: PacketInputs,
) -> None:
    # Feature: proof-packet, Property 7: Missing-note evidence is preserved and labelled
    member, status, findings, notes = inputs
    finding = findings[0]

    document = render_packet(member, status, findings=findings, notes=notes)
    parser = _parse(document)

    expected_evidence = "".join(
        (
            "<strong>Note ID:</strong> ",
            escape(finding.note_id, quote=True),
            " — ",
            escape(finding.quote, quote=True),
            "</li>",
        )
    )
    assert expected_evidence in document
    assert parser.mark_texts == []


@given(inputs=deterministic_packet_inputs())
@settings(max_examples=100)
def test_property_10_rendering_is_byte_deterministic(inputs: PacketInputs) -> None:
    # Feature: proof-packet, Property 10: Rendering is byte-deterministic
    member, status, findings, notes = inputs

    first = render_packet(member, status, findings=findings, notes=notes)
    second = render_packet(member, status, findings=findings, notes=notes)

    assert first == second
    assert first.encode("utf-8") == second.encode("utf-8")
