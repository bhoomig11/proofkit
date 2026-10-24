"""Focused examples for packet status labels and minimized member identity."""

from __future__ import annotations

from datetime import date
from html import escape
from html.parser import HTMLParser

import pytest

from proofkit.contracts import Member, OverallStatus, ProofKitStatus
from proofkit.integration.proof_packet import render_packet


MEMBER_ID = "SYN-9876"


class SectionTextParser(HTMLParser):
    """Collect non-blank decoded text nodes from each authored section."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sections: list[list[str]] = []
        self._current_section: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() == "section":
            assert self._current_section is None
            self._current_section = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "section" and self._current_section is not None:
            self.sections.append(self._current_section)
            self._current_section = None

    def handle_data(self, data: str) -> None:
        if self._current_section is not None and data.strip():
            self._current_section.append(data.strip())


def _member(
    *,
    display_name: str = "Status Test Member",
    eligibility_group: str = "expansion_adult",
    renewal_date: date = date(2025, 12, 31),
    phone_last4: str | None = None,
) -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name=display_name,
        eligibility_group=eligibility_group,
        renewal_date=renewal_date,
        phone_last4=phone_last4,
    )


def _status(
    overall_status: OverallStatus,
    *,
    protected_by: str | None = None,
) -> ProofKitStatus:
    return ProofKitStatus(
        member_id=MEMBER_ID,
        status=overall_status,
        protected_by=protected_by,
    )


def _section_text(document: str, heading: str) -> list[str]:
    parser = SectionTextParser()
    parser.feed(document)
    parser.close()
    matching_sections = [section for section in parser.sections if section and section[0] == heading]
    assert len(matching_sections) == 1
    return matching_sections[0]


@pytest.mark.parametrize(
    ("overall_status", "expected_label"),
    (
        (OverallStatus.PROTECTED, "Protected"),
        (OverallStatus.AT_RISK, "At risk"),
        (OverallStatus.NEEDS_REVIEW, "Needs review"),
    ),
)
def test_overall_status_uses_exact_plain_language_label(
    overall_status: OverallStatus,
    expected_label: str,
) -> None:
    """Validates: Requirements 7.1, 7.2, 7.3."""
    document = render_packet(_member(), _status(overall_status))

    assert _section_text(document, "Overall status") == [
        "Overall status",
        "Status:",
        expected_label,
    ]


def test_protected_by_is_escaped_text_in_status_section() -> None:
    """Validates: Requirement 7.4."""
    protected_by = 'exemption:<status-sentinel> & "quoted" \'reason\''

    document = render_packet(
        _member(),
        _status(OverallStatus.PROTECTED, protected_by=protected_by),
    )

    assert escape(protected_by, quote=True) in document
    assert _section_text(document, "Overall status") == [
        "Overall status",
        "Status:",
        "Protected",
        "Protected by:",
        protected_by,
    ]


def test_member_identity_includes_only_display_name_and_member_id() -> None:
    """Validates: Requirements 9.1, 9.2, 9.3, 9.4."""
    display_name = 'DISPLAY <identity-sentinel> & "quoted" \'name\''
    eligibility_group = "ELIGIBILITY-PRIVATE-SENTINEL"
    renewal_date = date(2042, 11, 23)
    phone_last4 = "7319"
    member = _member(
        display_name=display_name,
        eligibility_group=eligibility_group,
        renewal_date=renewal_date,
        phone_last4=phone_last4,
    )

    document = render_packet(member, _status(OverallStatus.NEEDS_REVIEW))
    identity_section = _section_text(document, "Member identity")
    identity_text = " ".join(identity_section)

    assert escape(display_name, quote=True) in document
    assert identity_section == [
        "Member identity",
        "Display name:",
        display_name,
        "Member ID:",
        MEMBER_ID,
    ]
    for restricted_value in (phone_last4, eligibility_group, renewal_date.isoformat()):
        assert restricted_value not in identity_text
    for restricted_field in ("phone_last4", "eligibility_group", "renewal_date"):
        assert restricted_field not in identity_text
