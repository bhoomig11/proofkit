"""Focused examples for statement, deadline, action, and disclaimer rendering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from html import escape
from html.parser import HTMLParser

from proofkit.contracts import (
    ActionItem,
    DecisionOutcome,
    ExemptionDecision,
    ExemptionType,
    Member,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration.packet import render_packet


MEMBER_ID = "SYN-0001"


@dataclass
class ParsedSection:
    heading: str = ""
    text_parts: list[str] = field(default_factory=list)
    items: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(" ".join(self.text_parts).split())


class SectionParser(HTMLParser):
    """Collect decoded section text and top-level list items."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[str] = []
        self.sections: list[ParsedSection] = []
        self._section: ParsedSection | None = None
        self._heading_parts: list[str] | None = None
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
            self._section.text_parts.append(data.strip())
        if self._heading_parts is not None:
            self._heading_parts.append(data)
        if self._item_depth:
            self._item_parts.append(data)


def _parse(document: str) -> SectionParser:
    parser = SectionParser()
    parser.feed(document)
    parser.close()
    return parser


def _section(parser: SectionParser, heading: str) -> ParsedSection:
    matches = [section for section in parser.sections if section.heading == heading]
    assert len(matches) == 1
    return matches[0]


def _member() -> Member:
    return Member(
        member_id=MEMBER_ID,
        display_name="Statement Test Member",
        renewal_date=date(2029, 12, 31),
    )


def _exemption(
    *,
    statement_draft: str | None,
    review_reasons: Sequence[str],
) -> ExemptionDecision:
    reasons = list(review_reasons)
    outcome = (
        DecisionOutcome.NEEDS_CLINICIAN_REVIEW
        if reasons
        else DecisionOutcome.NOT_EXEMPT
    )
    return ExemptionDecision(
        member_id=MEMBER_ID,
        outcome=outcome,
        exemption_type=ExemptionType.NONE,
        confidence=0.75,
        matched_rules=[],
        evidence_finding_ids=[],
        lookback_months=12,
        as_of=date(2030, 1, 15),
        rules_version="test-v1",
        review_reasons=reasons,
        statement_draft=statement_draft,
    )


def _wallet() -> WalletResult:
    return WalletResult(
        member_id=MEMBER_ID,
        records=[],
        months=[],
        verification_months=["2031-01"],
        next_renewal_date=date(2031, 3, 4),
        proof_due_date=date(2031, 2, 3),
        rules_version="test-v1",
    )


def _status(
    *,
    exemption: ExemptionDecision | None = None,
    wallet: WalletResult | None = None,
    next_deadline: date | None = None,
    action_items: Sequence[ActionItem] = (),
    disclaimer: str = "Required packet disclaimer.",
) -> ProofKitStatus:
    return ProofKitStatus(
        member_id=MEMBER_ID,
        status=OverallStatus.NEEDS_REVIEW,
        exemption=exemption,
        wallet=wallet,
        next_deadline=next_deadline,
        action_items=list(action_items),
        disclaimer=disclaimer,
    )


def test_absent_exemption_and_deadline_values_do_not_invent_content() -> None:
    """Validates: Requirements 4.3 and 4.9."""
    disclaimer = "Required disclaimer with no optional sections."

    document = render_packet(_member(), _status(disclaimer=disclaimer))
    parser = _parse(document)

    assert all(section.heading != "Clinician statement" for section in parser.sections)
    deadlines = _section(parser, "Deadlines and actions")
    assert deadlines.text == "Deadlines and actions"
    assert deadlines.items == []
    for absent_label in ("Next deadline:", "Proof due date:", "Next renewal date:", "Due:"):
        assert absent_label not in deadlines.text

    disclaimer_section = _section(parser, "Disclaimer")
    assert disclaimer_section.text == f"Disclaimer {disclaimer}"
    assert escape(disclaimer, quote=True) in document


def test_absent_statement_draft_preserves_ordered_escaped_review_reasons() -> None:
    """Validates: Requirements 4.1, 4.2 and 4.3."""
    reasons = [
        'FIRST reason <script>alert("reason")</script> & review',
        "SECOND reason <img src=x onerror='boom'> & follow-up",
    ]
    exemption = _exemption(statement_draft=None, review_reasons=reasons)

    document = render_packet(_member(), _status(exemption=exemption))
    parser = _parse(document)
    statement = _section(parser, "Clinician statement")

    assert "Statement draft:" not in statement.text
    assert statement.items == reasons
    escaped_reasons = [escape(reason, quote=True) for reason in reasons]
    assert all(document.count(reason) == 1 for reason in escaped_reasons)
    assert [document.index(reason) for reason in escaped_reasons] == sorted(
        document.index(reason) for reason in escaped_reasons
    )
    assert "script" not in parser.tags
    assert "img" not in parser.tags


def test_all_deadlines_use_iso_dates_and_actions_preserve_contract_order() -> None:
    """Validates: Requirements 4.4, 4.5, 4.6, 4.7 and 4.8."""
    next_deadline = date(2031, 1, 2)
    action_due = date(2031, 4, 5)
    actions = [
        ActionItem(
            priority=5,
            title="FIRST action despite lower urgency",
            detail="FIRST action detail",
            due=action_due,
        ),
        ActionItem(
            priority=1,
            title="SECOND action despite higher urgency",
            detail="SECOND action detail",
            due=None,
        ),
    ]

    document = render_packet(
        _member(),
        _status(
            wallet=_wallet(),
            next_deadline=next_deadline,
            action_items=actions,
        ),
    )
    deadlines = _section(_parse(document), "Deadlines and actions")

    expected_dates = (
        next_deadline,
        date(2031, 2, 3),
        date(2031, 3, 4),
        action_due,
    )
    for expected_date in expected_dates:
        rendered_date = expected_date.isoformat()
        assert rendered_date in deadlines.text
        assert document.count(rendered_date) == 1

    assert len(deadlines.items) == 2
    assert actions[0].title in deadlines.items[0]
    assert actions[0].detail in deadlines.items[0]
    assert action_due.isoformat() in deadlines.items[0]
    assert actions[1].title in deadlines.items[1]
    assert actions[1].detail in deadlines.items[1]
    assert "Due:" not in deadlines.items[1]
    assert "None" not in deadlines.items[1]


def test_adversarial_statement_action_and_disclaimer_are_escaped_text() -> None:
    """Validates: Requirements 4.1, 4.2, 4.7 and 4.9."""
    statement_draft = 'STATEMENT <script>alert("draft")</script> & \'quoted\''
    review_reason = 'REASON <svg onload="boom">x</svg> & \'quoted\''
    action_title = 'ACTION TITLE <img src=x onerror="boom"> & \'quoted\''
    action_detail = 'ACTION DETAIL </li><script>boom()</script> & "quoted"'
    disclaimer = 'DISCLAIMER </section><script>boom()</script> & \'quoted\''
    action = ActionItem(
        priority=1,
        title=action_title,
        detail=action_detail,
    )

    document = render_packet(
        _member(),
        _status(
            exemption=_exemption(
                statement_draft=statement_draft,
                review_reasons=[review_reason],
            ),
            action_items=[action],
            disclaimer=disclaimer,
        ),
    )
    parser = _parse(document)

    narrative_values = (
        statement_draft,
        review_reason,
        action_title,
        action_detail,
        disclaimer,
    )
    for value in narrative_values:
        assert document.count(escape(value, quote=True)) == 1

    statement = _section(parser, "Clinician statement")
    assert statement_draft in statement.text
    assert statement.items == [review_reason]
    action_section = _section(parser, "Deadlines and actions")
    assert action_title in action_section.items[0]
    assert action_detail in action_section.items[0]
    assert disclaimer in _section(parser, "Disclaimer").text
    assert not {"script", "img", "svg"}.intersection(parser.tags)
