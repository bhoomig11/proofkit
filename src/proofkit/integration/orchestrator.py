"""
FINAL owns this (built in the last 4-5 hours by the whole team).

Status rules (spec in tests/integration/test_status_rules.py and test_end_to_end.py):
  - exemption.outcome == EXEMPT                         -> PROTECTED, protected_by="exemption:<type>"
  - else every wallet.verification_month qualifies      -> PROTECTED, protected_by="compliance:<basis of last month>"
  - else any NEEDS_CLINICIAN_REVIEW / month needs_review -> NEEDS_REVIEW
  - else                                                -> AT_RISK, with action items (shortfall, due date)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from proofkit.common.llm import LLMClient
from proofkit.contracts import (
    ActionItem,
    ClinicalNote,
    DecisionOutcome,
    EarningsDocument,
    ExemptionDecision,
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.extraction import extract_findings
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules
from proofkit.wallet import build_wallet, load_wallet_rules


def month_label(month: str) -> str:
    """'2027-02' -> 'Feb 2027'."""
    year, mon = month.split("-")
    return date(int(year), int(mon), 1).strftime("%b %Y")


def money_label(amount: Decimal) -> str:
    """Decimal('60.00') -> '$60', Decimal('60.5') -> '$60.50'."""
    return f"${amount:,.0f}" if amount == amount.to_integral_value() else f"${amount:,.2f}"


def _shortfall_items(wallet: WalletResult, months: dict[str, MonthlyCompliance]) -> list[ActionItem]:
    items = []
    for m in wallet.verification_months:
        label = month_label(m)
        mc = months.get(m)
        if mc is None:
            items.append(ActionItem(priority=1, title=f"No proof yet for {label}",
                                    detail=f"Upload your pay statements for {label}.", due=wallet.proof_due_date))
        elif not mc.qualifies:
            items.append(ActionItem(
                priority=1, title=f"{money_label(mc.shortfall_income)} short in {label}",
                detail=(f"You need {money_label(mc.shortfall_income)} more income or "
                        f"{mc.shortfall_hours.normalize():f} more hours in {label} to meet the requirement."),
                due=wallet.proof_due_date))
    return items


def _options_items(due: date) -> list[ActionItem]:
    return [
        ActionItem(priority=2, title="Add a missing pay statement",
                   detail="Upload any gig or job earnings statement we don't have yet for that month.", due=due),
        ActionItem(priority=3, title="Log volunteer or school hours",
                   detail="Community service, job training, and school hours also count toward 80 hours.", due=due),
        ActionItem(priority=4, title="Ask a clinician about an exemption",
                   detail="A health condition may exempt you. Ask your clinic to review your records.", due=due),
    ]


def build_status(member: Member, exemption: ExemptionDecision | None, wallet: WalletResult | None, today: date) -> ProofKitStatus:
    """Member + ExemptionDecision? + WalletResult? -> ProofKitStatus, by the deterministic status rules above."""
    base = {"member_id": member.member_id, "exemption": exemption, "wallet": wallet}

    if exemption is not None and exemption.outcome == DecisionOutcome.EXEMPT:
        return ProofKitStatus(**base, status=OverallStatus.PROTECTED,
                              protected_by=f"exemption:{exemption.exemption_type.value}")

    months = {m.month: m for m in wallet.months} if wallet else {}
    verification = [months.get(m) for m in wallet.verification_months] if wallet else []
    if verification and all(mc is not None and mc.qualifies for mc in verification):
        return ProofKitStatus(**base, status=OverallStatus.PROTECTED,
                              protected_by=f"compliance:{verification[-1].basis.value}")

    due = wallet.proof_due_date if wallet else member.renewal_date
    clinician_review = exemption is not None and exemption.outcome == DecisionOutcome.NEEDS_CLINICIAN_REVIEW
    months_to_check = [mc for mc in verification if mc is not None and mc.needs_review]
    if clinician_review or months_to_check:
        items = []
        if clinician_review:
            items.append(ActionItem(priority=1, title="Get a clinician review",
                                    detail="Some health evidence needs a clinician to confirm it. "
                                           "Share your proof packet with your clinic.", due=due))
        for mc in months_to_check:
            items.append(ActionItem(priority=2, title=f"Re-upload proof for {month_label(mc.month)}",
                                    detail="We couldn't read one of your documents clearly. Upload a clearer copy.",
                                    due=due))
        return ProofKitStatus(**base, status=OverallStatus.NEEDS_REVIEW, next_deadline=due, action_items=items)

    items = (_shortfall_items(wallet, months) if wallet else []) + _options_items(due)
    return ProofKitStatus(**base, status=OverallStatus.AT_RISK, next_deadline=due,
                          action_items=sorted(items, key=lambda a: a.priority))


def run_member(member: Member, notes: list[ClinicalNote], docs: list[EarningsDocument], llm: LLMClient,
               frailty_rules_path: Path, wallet_rules_path: Path, today: date) -> ProofKitStatus:
    """Full pipeline for one member: extract -> decide (+ statement) -> wallet -> status.

    ClinicalNote[] + EarningsDocument[] -> ProofKitStatus. Rejected uploads raise ValueError (from the wallet).
    """
    bundle = extract_findings(notes, member.member_id, llm)
    decision = decide_exemption(bundle, member, load_frailty_rules(frailty_rules_path), today)
    if decision.outcome == DecisionOutcome.EXEMPT:
        statement = draft_statement(decision, bundle, member, llm)
        decision = ExemptionDecision.model_validate({**decision.model_dump(), "statement_draft": statement})
    wallet = build_wallet(member, docs, llm, load_wallet_rules(wallet_rules_path), today)
    return build_status(member, decision, wallet, today)
