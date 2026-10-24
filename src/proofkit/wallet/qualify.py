"""P2 owns this. DETERMINISTIC month-by-month compliance. No LLM, no I/O."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from proofkit.contracts import ComplianceBasis, EarningsRecord, MonthlyCompliance
from proofkit.wallet.rules import WalletRules

CENT = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def evaluate_months(records: list[EarningsRecord], rules: WalletRules) -> list[MonthlyCompliance]:
    """EarningsRecord[] -> MonthlyCompliance[] sorted by month. Pure."""
    by_month: dict[str, list[EarningsRecord]] = {}
    for r in records:
        by_month.setdefault(r.period_start.strftime("%Y-%m"), []).append(r)

    out = []
    for month, recs in sorted(by_month.items()):
        hours = _q(sum((r.hours for r in recs if r.hours is not None), Decimal("0")))
        income = _q(sum((r.gross_income for r in recs), Decimal("0")))
        if hours >= rules.monthly_hours_required:
            basis = ComplianceBasis.HOURS
        elif income >= rules.monthly_income_required:
            basis = ComplianceBasis.INCOME
        else:
            basis = ComplianceBasis.NONE
        out.append(MonthlyCompliance(
            month=month, total_hours=hours, hours_known_for_all_records=all(r.hours is not None for r in recs),
            total_income=income, qualifies=basis != ComplianceBasis.NONE, basis=basis,
            shortfall_hours=_q(max(Decimal("0"), rules.monthly_hours_required - hours)),
            shortfall_income=_q(max(Decimal("0"), rules.monthly_income_required - income)),
            record_ids=[r.record_id for r in recs],
        ))
    return out
