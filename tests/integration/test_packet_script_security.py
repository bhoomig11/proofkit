"""Focused security regressions for the Proof Packet HTML boundary."""

from datetime import date
from decimal import Decimal
from html import escape
from html.parser import HTMLParser

from proofkit.contracts import (
    ClinicalNote,
    EarningsRecord,
    Finding,
    FindingStatus,
    Member,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration.proof_packet import render_packet


CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
MEMBER_ID = "SYN-0001"


class PacketParser(HTMLParser):
    """Collect structural and visible-text facts from rendered packet HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.declarations: list[str] = []
        self.tags: list[str] = []
        self.attributes: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []

    def handle_decl(self, decl: str) -> None:
        self.declarations.append(decl.lower())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag.lower())
        self.attributes.append((tag.lower(), dict(attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Security Test Member",
        renewal_date=date(2025, 12, 31),
    )


def _status(*, wallet: WalletResult | None = None) -> ProofKitStatus:
    return ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.NEEDS_REVIEW,
        wallet=wallet,
    )


def _note(text: str, *, note_id: str = "note-1") -> ClinicalNote:
    return ClinicalNote(
        note_id=note_id,
        member_id=MEMBER_ID,
        note_date=date(2025, 1, 2),
        text=text,
    )


def _finding(quote: str, *, note_id: str, quote_start: int = 0, finding_id: str = "finding-1") -> Finding:
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


def _wallet_with_record(source_quote: str) -> WalletResult:
    record = EarningsRecord(
        record_id="record-1",
        member_id=MEMBER_ID,
        source_doc_id="document-1",
        platform="safe & sound",
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 7),
        hours=Decimal("12.50"),
        gross_income=Decimal("250.00"),
        source_quote=source_quote,
        confidence=Decimal("0.98"),
    )
    return WalletResult(
        member_id=MEMBER_ID,
        records=[record],
        months=[],
        verification_months=["2025-01"],
        next_renewal_date=date(2025, 12, 31),
        proof_due_date=date(2025, 2, 15),
        rules_version="test-v1",
    )


def _parse(document: str) -> PacketParser:
    parser = PacketParser()
    parser.feed(document)
    parser.close()
    return parser


def _assert_payload_is_inert_visible_text(document: str, payload: str) -> None:
    parser = _parse(document)
    assert escape(payload, quote=True) in document
    assert payload in "".join(parser.text)
    assert "script" not in parser.tags


def test_script_in_clinical_note_is_escaped_visible_text() -> None:
    payload = "Before <script>alert('note')</script> after"

    document = render_packet(_member(), _status(), notes=[_note(payload)])

    _assert_payload_is_inert_visible_text(document, payload)


def test_script_in_valid_finding_quote_is_escaped_visible_text() -> None:
    payload = "<script>alert('valid finding')</script>"
    note_text = f"Prefix {payload} suffix"
    quote_start = note_text.index(payload)
    note = _note(note_text)
    finding = _finding(payload, note_id=note.note_id, quote_start=quote_start)

    document = render_packet(_member(), _status(), findings=[finding], notes=[note])

    _assert_payload_is_inert_visible_text(document, payload)


def test_script_in_standalone_finding_quote_is_escaped_visible_text() -> None:
    payload = "<script>alert('standalone finding')</script>"
    finding = _finding(payload, note_id="missing-note")

    document = render_packet(_member(), _status(), findings=[finding])

    _assert_payload_is_inert_visible_text(document, payload)


def test_script_in_earnings_source_quote_is_escaped_visible_text() -> None:
    payload = "Gross pay <script>alert('earnings')</script> $250.00"
    wallet = _wallet_with_record(payload)

    document = render_packet(_member(), _status(wallet=wallet))

    _assert_payload_is_inert_visible_text(document, payload)
    assert escape("safe & sound", quote=True) in document


def test_default_render_is_one_self_contained_html_document() -> None:
    document = render_packet(_member(), _status())
    parser = _parse(document)

    assert parser.declarations == ["doctype html"]
    assert parser.tags.count("html") == 1
    assert parser.tags.count("head") == 1
    assert parser.tags.count("body") == 1
    assert parser.tags.count("style") == 1
    assert "script" not in parser.tags
    assert "link" not in parser.tags

    csp_values = [
        attrs.get("content")
        for tag, attrs in parser.attributes
        if tag == "meta" and (attrs.get("http-equiv") or "").lower() == "content-security-policy"
    ]
    assert csp_values == [CSP]

    url_attributes = {"src", "href", "action", "formaction", "poster"}
    assert all(not (url_attributes & attrs.keys()) for _, attrs in parser.attributes)
