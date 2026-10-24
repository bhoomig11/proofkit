"""P2 owns this. DETERMINISTIC month-by-month compliance. No LLM, no I/O."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from proofkit.contracts import ComplianceBasis, EarningsRecord, MonthlyCompliance
from proofkit.wallet.rules import WalletRules

CENT = Decimal("0.01")


class _Slice(NamedTuple):
    record_id: str
    hours: Decimal | None
    income: Decimal


def _q(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def _next_month(d: date) -> date:
    return (d.replace(day=1) + timedelta(days=32)).replace(day=1)


def _split_by_month(r: EarningsRecord) -> list[tuple[str, _Slice]]:
    """Prorate a record across calendar months by day count. Unrounded; rounding happens on the totals."""
    total_days = (r.period_end - r.period_start).days + 1
    out = []
    start = r.period_start
    while start <= r.period_end:
        end = min(r.period_end, _next_month(start) - timedelta(days=1))
        days = (end - start).days + 1
        hours = None if r.hours is None else r.hours * days / total_days
        out.append((start.strftime("%Y-%m"), _Slice(r.record_id, hours, r.gross_income * days / total_days)))
        start = end + timedelta(days=1)
    return out


def evaluate_months(records: list[EarningsRecord], rules: WalletRules) -> list[MonthlyCompliance]:
    """EarningsRecord[] -> MonthlyCompliance[] sorted by month. Pure."""
    by_month: dict[str, list[_Slice]] = {}
    reasons: dict[str, list[str]] = {}
    seen: dict[tuple, str] = {}  # (platform, period, hours, income) -> first source_doc_id
    for r in records:
        low = r.confidence < rules.min_record_confidence
        if not low:
            key = (r.platform, r.period_start, r.period_end, r.hours, r.gross_income)
            if seen.setdefault(key, r.source_doc_id) != r.source_doc_id:
                continue  # same statement uploaded twice
        for month, s in _split_by_month(r):
            by_month.setdefault(month, [])
            if low:
                reasons.setdefault(month, []).append(
                    f"record {r.record_id} excluded: confidence {r.confidence} below {rules.min_record_confidence}")
            else:
                by_month[month].append(s)

    out = []
    for month, slices in sorted(by_month.items()):
        hours = _q(sum((s.hours for s in slices if s.hours is not None), Decimal("0")))
        income = _q(sum((s.income for s in slices), Decimal("0")))
        if hours >= rules.monthly_hours_required:
            basis = ComplianceBasis.HOURS
        elif income >= rules.monthly_income_required:
            basis = ComplianceBasis.INCOME
        else:
            basis = ComplianceBasis.NONE
        out.append(MonthlyCompliance(
            month=month, total_hours=hours, hours_known_for_all_records=all(s.hours is not None for s in slices),
            total_income=income, qualifies=basis != ComplianceBasis.NONE, basis=basis,
            shortfall_hours=_q(max(Decimal("0"), rules.monthly_hours_required - hours)),
            shortfall_income=_q(max(Decimal("0"), rules.monthly_income_required - income)),
            record_ids=[s.record_id for s in slices],
            needs_review=month in reasons, review_reasons=reasons.get(month, []),
        ))
    return out
