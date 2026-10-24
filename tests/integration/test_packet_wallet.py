"""Focused examples for monthly compliance and wallet evidence rendering."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from html import escape
from html.parser import HTMLParser
from typing import Sequence

import pytest

from proofkit.contracts import (
    ComplianceBasis,
    EarningsRecord,
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration import proof_packet as packet_module
from proofkit.integration.proof_packet import render_packet


MEMBER_ID = "SYN-0001"
EXPECTED_HEADERS = [
    "Month",
    "Hours",
    "Income",
    "Qualifies",
    "Basis",
    "Shortfall hours",
    "Shortfall income",
    "Needs review",
    "Review reasons",
]


@dataclass
class ParsedSection:
    heading: str = ""
    table_count: int = 0
    tbody_count: int = 0
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    items: list[str] = field(default_factory=list)
    text: list[str] = field(default_factory=list)


class WalletParser(HTMLParser):
    """Collect decoded section, table, and list content from packet HTML."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.sections: list[ParsedSection] = []
        self._section: ParsedSection | None = None
        self._heading_parts: list[str] | None = None
        self._cell_kind: str | None = None
        self._cell_parts: list[str] = []
        self._row: list[str] | None = None
        self._in_tbody = False
        self._item_depth = 0
        self._item_parts: list[str] = []

    @staticmethod
    def _normalized(parts: list[str]) -> str:
        return " ".join("".join(parts).split())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        tag = tag.lower()
        self.tags.append(tag)
        if tag == "section":
            assert self._section is None
            self._section = ParsedSection()
        elif self._section is not None and tag == "h2":
            self._heading_parts = []
        elif self._section is not None and tag == "table":
            self._section.table_count += 1
        elif self._section is not None and tag == "tbody":
            self._section.tbody_count += 1
            self._in_tbody = True
        elif self._section is not None and tag == "tr" and self._in_tbody:
            self._row = []
        elif self._section is not None and tag in {"th", "td"}:
            self._cell_kind = tag
            self._cell_parts = []
        elif self._section is not None and tag == "li":
            if self._item_depth == 0:
                self._item_parts = []
            self._item_depth += 1

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._section is None:
            return
        if tag == "h2" and self._heading_parts is not None:
            self._section.heading = self._normalized(self._heading_parts)
            self._heading_parts = None
        elif tag == "th" and self._cell_kind == "th":
            self._section.headers.append(self._normalized(self._cell_parts))
            self._cell_kind = None
        elif tag == "td" and self._cell_kind == "td":
            assert self._row is not None
            self._row.append(self._normalized(self._cell_parts))
            self._cell_kind = None
        elif tag == "tr" and self._in_tbody:
            assert self._row is not None
            self._section.rows.append(self._row)
            self._row = None
        elif tag == "tbody":
            self._in_tbody = False
        elif tag == "li" and self._item_depth:
            self._item_depth -= 1
            if self._item_depth == 0:
                self._section.items.append(self._normalized(self._item_parts))
        elif tag == "section":
            self.sections.append(self._section)
            self._section = None

    def handle_data(self, data: str) -> None:
        if self._section is None:
            return
        if data.strip():
            self._section.text.append(data.strip())
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._cell_kind is not None:
            self._cell_parts.append(data)
        if self._item_depth:
            self._item_parts.append(data)


def _parse(document: str) -> WalletParser:
    parser = WalletParser()
    parser.feed(document)
    parser.close()
    return parser


def _section(parser: WalletParser, heading: str) -> ParsedSection:
    matches = [section for section in parser.sections if section.heading == heading]
    assert len(matches) == 1
    return matches[0]


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Wallet Test Member",
        renewal_date=date(2025, 12, 31),
    )


def _status(wallet: WalletResult | None = None) -> ProofKitStatus:
    return ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.NEEDS_REVIEW,
        wallet=wallet,
    )


def _month(
    *,
    month: str = "2025-01",
    total_hours: Decimal = Decimal("0"),
    total_income: Decimal = Decimal("0"),
    qualifies: bool = False,
    basis: ComplianceBasis = ComplianceBasis.NONE,
    shortfall_hours: Decimal = Decimal("0"),
    shortfall_income: Decimal = Decimal("0"),
    needs_review: bool = False,
    review_reasons: Sequence[str] = (),
) -> MonthlyCompliance:
    return MonthlyCompliance(
        month=month,
        total_hours=total_hours,
        hours_known_for_all_records=True,
        total_income=total_income,
        qualifies=qualifies,
        basis=basis,
        shortfall_hours=shortfall_hours,
        shortfall_income=shortfall_income,
        record_ids=[],
        needs_review=needs_review,
        review_reasons=list(review_reasons),
    )


def _record(
    *,
    record_id: str,
    platform: str,
    source_quote: str,
) -> EarningsRecord:
    return EarningsRecord(
        record_id=record_id,
        member_id=MEMBER_ID,
        source_doc_id=f"document-{record_id}",
        platform=platform,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 7),
        hours=Decimal("12.50"),
        gross_income=Decimal("250.00"),
        source_quote=source_quote,
        confidence=Decimal("0.98"),
    )


def _wallet(
    *,
    months: Sequence[MonthlyCompliance] = (),
    records: Sequence[EarningsRecord] = (),
) -> WalletResult:
    return WalletResult(
        member_id=MEMBER_ID,
        records=list(records),
        months=list(months),
        verification_months=["2025-01"],
        next_renewal_date=date(2025, 12, 31),
        proof_due_date=date(2025, 2, 15),
        rules_version="test-v1",
    )


def test_no_wallet_omits_monthly_table_and_wallet_evidence() -> None:
    """Validates: Requirement 8.6."""
    document = render_packet(_member(), _status())
    parser = _parse(document)

    assert "table" not in parser.tags
    assert all(section.heading != "Monthly compliance" for section in parser.sections)
    assert all(section.heading != "Wallet evidence" for section in parser.sections)


def test_empty_months_retains_headers_and_empty_tbody() -> None:
    """Validates: Requirement 8.7."""
    document = render_packet(_member(), _status(_wallet()))
    monthly = _section(_parse(document), "Monthly compliance")

    assert monthly.table_count == 1
    assert monthly.tbody_count == 1
    assert monthly.headers == EXPECTED_HEADERS
    assert monthly.rows == []


def test_month_rows_preserve_source_order_and_include_required_fields() -> None:
    """Validates: Requirements 8.1 and 8.5."""
    review_reasons = (
        'Hours need <review> & "confirmation"',
        "Second reason with 'quotes'",
    )
    first = _month(
        month="2025-11",
        total_hours=Decimal("0"),
        total_income=Decimal("0.01"),
        shortfall_hours=Decimal("80.5"),
        shortfall_income=Decimal("1479.99"),
        needs_review=True,
        review_reasons=review_reasons,
    )
    second = _month(
        month="2025-02",
        total_hours=Decimal("92.5"),
        total_income=Decimal("1480"),
        qualifies=True,
        basis=ComplianceBasis.HOURS,
        shortfall_hours=Decimal("0.01"),
        shortfall_income=Decimal("0"),
    )

    document = render_packet(_member(), _status(_wallet(months=[first, second])))
    monthly = _section(_parse(document), "Monthly compliance")

    assert len(monthly.rows) == 2
    assert [row[0] for row in monthly.rows] == ["2025-11", "2025-02"]
    assert monthly.rows[0][:8] == [
        "2025-11",
        "0.00",
        "$0.01",
        "No",
        "none",
        "80.50",
        "$1,479.99",
        "Yes",
    ]
    assert monthly.rows[1][:8] == [
        "2025-02",
        "92.50",
        "$1,480.00",
        "Yes",
        "hours",
        "0.01",
        "$0.00",
        "No",
    ]
    assert all(len(row) == len(EXPECTED_HEADERS) for row in monthly.rows)
    assert all(reason in monthly.rows[0][8] for reason in review_reasons)
    assert monthly.rows[1][8] == ""
    for reason in review_reasons:
        assert escape(reason, quote=True) in document


@pytest.mark.parametrize(
    (
        "total_hours",
        "total_income",
        "shortfall_hours",
        "shortfall_income",
        "expected_values",
    ),
    (
        (
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
            ("0.00", "$0.00", "0.00", "$0.00"),
        ),
        (
            Decimal("0.01"),
            Decimal("0.01"),
            Decimal("0.01"),
            Decimal("0.01"),
            ("0.01", "$0.01", "0.01", "$0.01"),
        ),
        (
            Decimal("92.5"),
            Decimal("1480"),
            Decimal("7.25"),
            Decimal("19.9"),
            ("92.50", "$1,480.00", "7.25", "$19.90"),
        ),
        (
            Decimal("12345.67"),
            Decimal("1234567.89"),
            Decimal("10000.1"),
            Decimal("9876543.21"),
            ("12345.67", "$1,234,567.89", "10000.10", "$9,876,543.21"),
        ),
        (
            Decimal("744.00"),
            Decimal("9999999999.99"),
            Decimal("744.00"),
            Decimal("9999999999.99"),
            ("744.00", "$9,999,999,999.99", "744.00", "$9,999,999,999.99"),
        ),
    ),
)
def test_decimal_values_have_exact_fixed_precision_and_direct_grouping(
    total_hours: Decimal,
    total_income: Decimal,
    shortfall_hours: Decimal,
    shortfall_income: Decimal,
    expected_values: tuple[str, str, str, str],
) -> None:
    """Validates: Requirements 8.2, 8.3 and 8.4."""
    month = _month(
        total_hours=total_hours,
        total_income=total_income,
        shortfall_hours=shortfall_hours,
        shortfall_income=shortfall_income,
    )

    document = render_packet(_member(), _status(_wallet(months=[month])))
    row = _section(_parse(document), "Monthly compliance").rows[0]

    assert (row[1], row[2], row[5], row[6]) == expected_values
    assert all("e" not in value.lower() for value in expected_values)


def test_wallet_decimal_rendering_never_calls_float() -> None:
    """Validates: Requirement 8.4."""
    tree = ast.parse(inspect.getsource(packet_module))
    float_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "float"
    ]

    assert float_calls == []


def test_wallet_evidence_is_escaped_ordered_and_rendered_once() -> None:
    """Validates: Requirements 2.1, 2.3 and 2.4."""
    first_platform = 'first-platform<script data-x="1">&'
    first_quote = 'FIRST-QUOTE <img src=x onerror="boom"> & paid'
    second_platform = "second-platform & <b>markup</b>"
    second_quote = "SECOND-QUOTE javascript:alert('x') <script>x</script>"
    records = [
        _record(record_id="record-2", platform=first_platform, source_quote=first_quote),
        _record(record_id="record-1", platform=second_platform, source_quote=second_quote),
    ]

    document = render_packet(_member(), _status(_wallet(records=records)))
    parser = _parse(document)
    evidence = _section(parser, "Wallet evidence")

    assert len(evidence.items) == 2
    assert evidence.items == [
        f"Platform: {first_platform} Source quote: {first_quote}",
        f"Platform: {second_platform} Source quote: {second_quote}",
    ]
    escaped_values = [
        escape(first_platform, quote=True),
        escape(first_quote, quote=True),
        escape(second_platform, quote=True),
        escape(second_quote, quote=True),
    ]
    assert all(document.count(value) == 1 for value in escaped_values)
    assert [document.index(value) for value in escaped_values] == sorted(
        document.index(value) for value in escaped_values
    )
    assert "script" not in parser.tags
    assert "img" not in parser.tags
