"""Framework-neutral member view construction and LLM selection."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from proofkit.common.llm import AnthropicClient, LLMClient, LLMError
from proofkit.contracts import DecisionOutcome, ExemptionDecision, FindingsBundle, Member, ProofKitStatus, WalletResult
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
    exemption: ExemptionDecision
    wallet: WalletResult
    status: ProofKitStatus


def build_member_view(member_id: str, data: DemoData, llm: LLMClient,
                      frailty_rules_path: Path, wallet_rules_path: Path) -> MemberView:
    """Run public ProofKit APIs and retain the FindingsBundle needed by the UI."""
    if member_id not in data.members:
        raise ValueError(f"unknown synthetic persona: {member_id}")
    member = data.members[member_id]
    findings = extract_findings(data.notes.get(member_id, []), member_id, llm)
    exemption = decide_exemption(findings, member, load_frailty_rules(frailty_rules_path), data.today)
    if exemption.outcome == DecisionOutcome.EXEMPT:
        statement = draft_statement(exemption, findings, member, llm)
        exemption = exemption.model_copy(update={"statement_draft": statement})
    wallet = build_wallet(
        member,
        data.documents.get(member_id, []),
        llm,
        load_wallet_rules(wallet_rules_path),
        data.today,
    )
    status = build_status(member, exemption, wallet, data.today)
    return MemberView(member=member, findings=findings, exemption=exemption, wallet=wallet, status=status)


def make_llm(*, live: bool, data: DemoData) -> tuple[LLMClient, bool]:
    """Choose a live client when available, otherwise return deterministic offline replay."""
    if live:
        try:
            return AnthropicClient(), True
        except (LLMError, ImportError):
            pass
    return make_offline_llm(data), False
