"""Framework-neutral member view construction and LLM selection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from proofkit.common.llm import AnthropicClient, LLMClient, LLMError
from proofkit.contracts import (ClinicalNote, DecisionOutcome, EarningsDocument, ExemptionDecision, FindingsBundle,
                                Member, ProofKitStatus, WalletResult)
from proofkit.extraction import extract_findings
from proofkit.integration import build_status
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules
from proofkit.wallet import build_wallet, load_wallet_rules

from app.data import DemoData
from app.offline import make_offline_llm


@dataclass(frozen=True)
class MemberView:
    member: Member
    findings: FindingsBundle
    exemption: ExemptionDecision | None     # None when the member has no clinical notes yet
    wallet: WalletResult | None             # None when the member has no earnings documents yet
    status: ProofKitStatus


def build_view(member: Member, notes: list[ClinicalNote], documents: list[EarningsDocument], llm: LLMClient,
               frailty_rules_path: Path, wallet_rules_path: Path, today: date) -> MemberView:
    """Run the public ProofKit pipeline on one member's own documents and keep the FindingsBundle for the UI."""
    if notes:
        findings = extract_findings(notes, member.member_id, llm)
        exemption = decide_exemption(findings, member, load_frailty_rules(frailty_rules_path), today)
        if exemption.outcome == DecisionOutcome.EXEMPT:
            exemption = exemption.model_copy(
                update={"statement_draft": draft_statement(exemption, findings, member, llm)})
    else:
        findings = FindingsBundle(member_id=member.member_id, notes_processed=[], findings=[],
                                  extractor_version="none")
        exemption = None
    wallet = build_wallet(member, documents, llm, load_wallet_rules(wallet_rules_path), today) if documents else None
    status = build_status(member, exemption, wallet, today)
    return MemberView(member=member, findings=findings, exemption=exemption, wallet=wallet, status=status)


def build_member_view(member_id: str, data: DemoData, llm: LLMClient,
                      frailty_rules_path: Path, wallet_rules_path: Path) -> MemberView:
    """A synthetic demo member's view, from the fixture documents."""
    if member_id not in data.members:
        raise ValueError(f"unknown synthetic persona: {member_id}")
    return build_view(data.members[member_id], data.notes.get(member_id, []), data.documents.get(member_id, []),
                      llm, frailty_rules_path, wallet_rules_path, data.today)


def make_llm(*, live: bool, data: DemoData) -> tuple[LLMClient, bool]:
    """Choose a live client when available, otherwise return deterministic offline replay."""
    if live:
        try:
            return AnthropicClient(), True
        except (LLMError, ImportError):
            pass
    return make_offline_llm(data), False
