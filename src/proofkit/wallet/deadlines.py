"""P2 owns this. Verification months + proof due date from the renewal date. Pure date math."""
from __future__ import annotations

from datetime import date

from proofkit.contracts import Member
from proofkit.wallet.rules import WalletRules


def compute_deadlines(member: Member, rules: WalletRules) -> tuple[list[str], date]:
    """Return (verification_months as 'YYYY-MM', proof_due_date)."""
    raise NotImplementedError("P2: implement test-first")
