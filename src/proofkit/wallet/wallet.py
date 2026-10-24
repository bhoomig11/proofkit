"""P2 owns this. Glue: parse -> evaluate -> deadlines -> WalletResult."""
from __future__ import annotations

from datetime import date

from proofkit.common.llm import LLMClient
from proofkit.contracts import EarningsDocument, Member, WalletResult
from proofkit.wallet.rules import WalletRules


def build_wallet(member: Member, docs: list[EarningsDocument], llm: LLMClient, rules: WalletRules, today: date) -> WalletResult:
    raise NotImplementedError("P2: implement test-first")
