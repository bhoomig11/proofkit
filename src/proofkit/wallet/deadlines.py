"""P2 owns this. Verification months + proof due date from the renewal date. Pure date math."""
from __future__ import annotations

from datetime import date, timedelta

from proofkit.contracts import Member
from proofkit.wallet.rules import WalletRules


def compute_deadlines(member: Member, rules: WalletRules) -> tuple[list[str], date]:
    """Member -> (verification_months as 'YYYY-MM' oldest first, proof_due_date). Pure."""
    months = []
    d = member.renewal_date.replace(day=1)
    for _ in range(rules.verification_months_before_renewal):
        d = (d - timedelta(days=1)).replace(day=1)
        months.append(d.strftime("%Y-%m"))
    return sorted(months), member.renewal_date - timedelta(days=rules.proof_buffer_days)
