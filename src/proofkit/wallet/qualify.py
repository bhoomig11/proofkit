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
    excluded: dict[str, str] = {}  # record_id -> why it doesn't count
    kept: list[EarningsRecord] = []
    seen: dict[tuple, str] = {}  # (platform, period, hours, income) -> first source_doc_id
    for r in records:
        if r.confidence < rules.min_record_confidence:
            excluded[r.record_id] = f"confidence {r.confidence} below {rules.min_record_confidence}"
            continue
        key = (r.platform, r.period_start, r.period_end, r.hours, r.gross_income)
        if seen.setdefault(key, r.source_doc_id) == r.source_doc_id:
            kept.append(r)  # otherwise: same statement uploaded twice
    # Same platform, overlapping days, and a different document or a different period (a monthly total next to a
    # weekly line): we can't tell which is right, so neither counts until someone reviews it. Identical periods in
    # one document can be separate gigs and both count. ponytail: O(n^2) pairs, fine for a few dozen records.
    for a in kept:
        for b in kept:
            if (a.platform == b.platform and a.period_start <= b.period_end and b.period_start <= a.period_end
                    and (a.source_doc_id != b.source_doc_id
                         or (a.period_start, a.period_end) != (b.period_start, b.period_end))):
                excluded[a.record_id] = f"overlaps {b.record_id} from another {a.platform} statement"

    counted = {r.record_id for r in kept} - excluded.keys()
    by_month: dict[str, list[_Slice]] = {}
    reasons: dict[str, list[str]] = {}
    for r in records:
        for month, s in _split_by_month(r):
            by_month.setdefault(month, [])
            if r.record_id in excluded:
                reasons.setdefault(month, []).append(f"record {r.record_id} excluded: {excluded[r.record_id]}")
            elif r.record_id in counted:
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
