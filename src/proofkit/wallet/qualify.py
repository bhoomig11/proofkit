"""P2 owns this. DETERMINISTIC month-by-month compliance. No LLM, no I/O."""
from __future__ import annotations

from proofkit.contracts import EarningsRecord, MonthlyCompliance
from proofkit.wallet.rules import WalletRules


def evaluate_months(records: list[EarningsRecord], rules: WalletRules) -> list[MonthlyCompliance]:
    raise NotImplementedError("P2: implement test-first")
