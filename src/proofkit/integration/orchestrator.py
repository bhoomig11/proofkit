"""
FINAL owns this (built in the last 4-5 hours by the whole team).

Status rules (spec in tests/integration/test_end_to_end.py):
  - exemption.outcome == EXEMPT                         -> PROTECTED, protected_by="exemption:<type>"
  - else every wallet.verification_month qualifies      -> PROTECTED, protected_by="compliance:<basis of last month>"
  - else any NEEDS_CLINICIAN_REVIEW / month needs_review -> NEEDS_REVIEW
  - else                                                -> AT_RISK, with action items (shortfall, due date)
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from proofkit.common.llm import LLMClient
from proofkit.contracts import ClinicalNote, EarningsDocument, ExemptionDecision, Member, ProofKitStatus, WalletResult


def build_status(member: Member, exemption: ExemptionDecision | None, wallet: WalletResult | None, today: date) -> ProofKitStatus:
    raise NotImplementedError("FINAL: implement test-first")


def run_member(member: Member, notes: list[ClinicalNote], docs: list[EarningsDocument], llm: LLMClient,
               frailty_rules_path: Path, wallet_rules_path: Path, today: date) -> ProofKitStatus:
    """Full pipeline for one member: extract -> decide (+ statement) -> wallet -> status."""
    raise NotImplementedError("FINAL: implement test-first")
