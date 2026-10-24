"""Parser-based capability confinement tests for Proof Packet HTML."""

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


class CapabilityParser(HTMLParser):
    """Separate authored elements/attributes from decoded text-node content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.elements: list[tuple[str, tuple[tuple[str, str | None], ...]]] = []
        self.text_nodes: list[str] = []
        self.style_blocks: list[str] = []
        self.style_locations: list[bool] = []
        self._in_head = False
        self._style_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        normalized_tag = tag.lower()
        normalized_attrs = tuple((name.lower(), value) for name, value in attrs)
        self.elements.append((normalized_tag, normalized_attrs))
        if normalized_tag == "head":
            self._in_head = True
        elif normalized_tag == "style":
            self.style_locations.append(self._in_head)
            self._style_chunks = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "style" and self._style_chunks is not None:
            self.style_blocks.append("".join(self._style_chunks))
            self._style_chunks = None
        elif normalized_tag == "head":
            self._in_head = False

    def handle_data(self, data: str) -> None:
        if self._style_chunks is not None:
            self._style_chunks.append(data)
        else:
            self.text_nodes.append(data)


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Capability Test Member",
        renewal_date=date(2025, 12, 31),
    )


def _render_with_payloads(
    *,
    note_payload: str,
    finding_payload: str,
    platform_payload: str,
    source_quote_payload: str,
) -> str:
    note_text = f"{note_payload}\nFinding evidence: {finding_payload}"
    quote_start = note_text.index(finding_payload)
    note = ClinicalNote(
        note_id="note-1",
        member_id=MEMBER_ID,
        note_date=date(2025, 1, 2),
        text=note_text,
    )
    finding = Finding(
        finding_id="finding-1",
        note_id=note.note_id,
        note_date=note.note_date,
        condition="Test condition",
        icd10="M32.9",
        status=FindingStatus.CURRENT,
        quote=finding_payload,
        quote_start=quote_start,
        quote_end=quote_start + len(finding_payload),
        confidence=0.99,
    )
    record = EarningsRecord(
        record_id="record-1",
        member_id=MEMBER_ID,
        source_doc_id="document-1",
        platform=platform_payload,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 7),
        hours=Decimal("12.50"),
        gross_income=Decimal("250.00"),
        source_quote=source_quote_payload,
        confidence=0.98,
    )
    wallet = WalletResult(
        member_id=MEMBER_ID,
        records=[record],
        months=[],
        verification_months=["2025-01"],
        next_renewal_date=date(2025, 12, 31),
        proof_due_date=date(2025, 2, 15),
        rules_version="test-v1",
    )
    status = ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.NEEDS_REVIEW,
        wallet=wallet,
    )
    return render_packet(_member(), status, findings=[finding], notes=[note])


def _parse(document: str) -> CapabilityParser:
    parser = CapabilityParser()
    parser.feed(document)
    parser.close()
    return parser


def _attribute_map(attrs: tuple[tuple[str, str | None], ...]) -> dict[str, str | None]:
    return dict(attrs)


def test_packet_uses_exact_csp_and_only_inline_authored_styles() -> None:
    document = _render_with_payloads(
        note_payload="ordinary note",
        finding_payload="ordinary finding",
        platform_payload="ordinary platform",
        source_quote_payload="ordinary source quote",
    )
    parser = _parse(document)

    csp_values = [
        _attribute_map(attrs).get("content")
        for tag, attrs in parser.elements
        if tag == "meta"
        and (_attribute_map(attrs).get("http-equiv") or "").lower() == "content-security-policy"
    ]
    assert csp_values == [CSP]
    assert parser.style_locations == [True]
    assert len(parser.style_blocks) == 1
    assert parser.style_blocks[0].strip()
    assert "link" not in [tag for tag, _ in parser.elements]
    assert "@import" not in parser.style_blocks[0].lower()
    assert "url(" not in parser.style_blocks[0].lower()


def test_adversarial_text_cannot_add_elements_attributes_or_resource_references() -> None:
    payloads = (
        "Note <ScRiPt SRC='https://evil.example/n.js'>alert(1)</ScRiPt> &lt;script&gt;",
        'Finding </p><IFRAME SRC="javascript:alert(2)" ONLOAD="alert(3)"> &amp;#x3c;script&amp;#x3e;',
        '"><IMG SRC=//evil.example/p ONERROR=alert(4)>',
        "Quote <LiNk HREF='https://evil.example/x.css'> &NewLine; JaVaScRiPt:alert(5)",
    )
    adversarial_document = _render_with_payloads(
        note_payload=payloads[0],
        finding_payload=payloads[1],
        platform_payload=payloads[2],
        source_quote_payload=payloads[3],
    )
    benign_document = _render_with_payloads(
        note_payload="benign note text",
        finding_payload="benign finding text",
        platform_payload="benign platform",
        source_quote_payload="benign source quote",
    )
    adversarial = _parse(adversarial_document)
    benign = _parse(benign_document)

    assert adversarial.elements == benign.elements
    visible_text = "".join(adversarial.text_nodes)
    for payload in payloads:
        assert escape(payload, quote=True) in adversarial_document
        assert payload in visible_text

    tags = [tag for tag, _ in adversarial.elements]
    assert "script" not in tags
    assert "iframe" not in tags
    assert "img" not in tags
    assert "link" not in tags

    for _, attrs in adversarial.elements:
        for name, value in attrs:
            assert not name.startswith("on")
            if name in URL_ATTRIBUTES and value is not None:
                assert "javascript:" not in value.lower()
                normalized_value = value.strip().lower()
                assert normalized_value.startswith(("data:", "#"))
