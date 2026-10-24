"""build_status rules (docs/roles/FINAL_INTEGRATION_UI.md §Status rules), on hand-built contract objects."""
from datetime import date
from decimal import Decimal

from proofkit.contracts import (
    ComplianceBasis,
    DecisionOutcome,
    ExemptionDecision,
    ExemptionType,
    MatchedRule,
    Member,
    MonthlyCompliance,
    OverallStatus,
    WalletResult,
)
from proofkit.integration import build_status

TODAY = date(2027, 3, 1)
DUE = date(2027, 3, 6)
MEMBER = Member(member_id="SYN-0009", display_name="Test (synthetic)", renewal_date=date(2027, 3, 20))


def decision(outcome: DecisionOutcome, statement: str | None = None) -> ExemptionDecision:
    exempt = outcome == DecisionOutcome.EXEMPT
    return ExemptionDecision(
        member_id="SYN-0009", outcome=outcome,
        exemption_type=ExemptionType.MEDICALLY_FRAIL if exempt else ExemptionType.NONE,
        confidence=0.9,
        matched_rules=[MatchedRule(rule_id="R1", category="serious_complex_medical", finding_ids=["F-1"],
                                   rationale="lupus")] if exempt else [],
        evidence_finding_ids=["F-1"] if exempt else [],
        lookback_months=12, as_of=TODAY, rules_version="t",
        review_reasons=["borderline confidence"] if outcome == DecisionOutcome.NEEDS_CLINICIAN_REVIEW else [],
        statement_draft=statement,
    )


def month(m: str, *, hours: str = "0", income: str = "0", basis: ComplianceBasis = ComplianceBasis.NONE,
          short_h: str = "0", short_i: str = "0", needs_review: bool = False) -> MonthlyCompliance:
    return MonthlyCompliance(
        month=m, total_hours=Decimal(hours), hours_known_for_all_records=True, total_income=Decimal(income),
        qualifies=basis != ComplianceBasis.NONE, basis=basis, shortfall_hours=Decimal(short_h),
        shortfall_income=Decimal(short_i), record_ids=[], needs_review=needs_review,
        review_reasons=["unreadable upload"] if needs_review else [],
    )


def wallet(*months: MonthlyCompliance, verification: tuple[str, ...] = ("2027-02",)) -> WalletResult:
    return WalletResult(member_id="SYN-0009", records=[], months=list(months), verification_months=list(verification),
                        next_renewal_date=date(2027, 3, 20), proof_due_date=DUE, rules_version="t")


PASSING_FEB = month("2027-02", hours="92.5", income="700", basis=ComplianceBasis.HOURS)
FAILING_FEB = month("2027-02", hours="30", income="520", short_h="50", short_i="60")


def test_exempt_is_protected_by_exemption_type_with_statement():
    st = build_status(MEMBER, decision(DecisionOutcome.EXEMPT, "Statement."), wallet(FAILING_FEB), TODAY)
    assert st.status == OverallStatus.PROTECTED
    assert st.protected_by == "exemption:medically_frail"
    assert st.exemption.statement_draft == "Statement."


def test_exempt_wins_even_without_a_wallet():
    st = build_status(MEMBER, decision(DecisionOutcome.EXEMPT, "S."), None, TODAY)
    assert st.protected_by == "exemption:medically_frail"


def test_all_verification_months_qualifying_is_protected_by_last_months_basis():
    jan = month("2027-01", income="900", basis=ComplianceBasis.INCOME)
    st = build_status(MEMBER, decision(DecisionOutcome.NOT_EXEMPT), wallet(jan, PASSING_FEB,
                      verification=("2027-01", "2027-02")), TODAY)
    assert st.status == OverallStatus.PROTECTED
    assert st.protected_by == "compliance:hours"


def test_missing_verification_month_is_not_protected():
    st = build_status(MEMBER, decision(DecisionOutcome.NOT_EXEMPT), wallet(month("2027-01", income="900",
                      basis=ComplianceBasis.INCOME)), TODAY)
    assert st.status == OverallStatus.AT_RISK


def test_clinician_review_is_needs_review_with_action():
    st = build_status(MEMBER, decision(DecisionOutcome.NEEDS_CLINICIAN_REVIEW), wallet(FAILING_FEB), TODAY)
    assert st.status == OverallStatus.NEEDS_REVIEW
    assert st.protected_by is None
    assert any("clinician" in a.title.lower() for a in st.action_items)


def test_month_needing_review_is_needs_review_with_reupload_action():
    feb = month("2027-02", income="520", short_h="80", short_i="60", needs_review=True)
    st = build_status(MEMBER, decision(DecisionOutcome.NOT_EXEMPT), wallet(feb), TODAY)
    assert st.status == OverallStatus.NEEDS_REVIEW
    assert any("upload" in a.title.lower() for a in st.action_items)
    assert st.next_deadline == DUE


def test_compliance_beats_clinician_review():
    st = build_status(MEMBER, decision(DecisionOutcome.NEEDS_CLINICIAN_REVIEW), wallet(PASSING_FEB), TODAY)
    assert st.status == OverallStatus.PROTECTED


def test_at_risk_names_the_dollar_shortfall_options_and_deadline():
    st = build_status(MEMBER, decision(DecisionOutcome.NOT_EXEMPT), wallet(FAILING_FEB), TODAY)
    assert st.status == OverallStatus.AT_RISK
    assert st.protected_by is None
    assert st.next_deadline == DUE
    text = " ".join(f"{a.title} {a.detail}" for a in st.action_items)
    assert "$60 short in Feb 2027" in text
    assert "pay statement" in text and "volunteer" in text and "clinician" in text
    assert [a.priority for a in st.action_items] == sorted(a.priority for a in st.action_items)


def test_at_risk_with_no_inputs_still_has_actions_and_a_deadline():
    st = build_status(MEMBER, None, None, TODAY)
    assert st.status == OverallStatus.AT_RISK
    assert st.action_items
    assert st.next_deadline == MEMBER.renewal_date


def test_status_always_carries_disclaimer_and_member():
    st = build_status(MEMBER, None, wallet(PASSING_FEB), TODAY)
    assert st.member_id == "SYN-0009"
    assert "MassHealth makes all eligibility determinations" in st.disclaimer
