"""What-if: re-run the wallet's real rules and build_status on a copy. The real status never changes."""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from proofkit.contracts import EarningsRecord, MonthlyCompliance, ProofKitStatus, WalletResult
from proofkit.integration import build_status
from proofkit.wallet import WalletRules, evaluate_months


def target_month(wallet: WalletResult) -> str:
    """The month the member most needs: the first verification month that does not qualify."""
    by_month = {m.month: m for m in wallet.months}
    for month in wallet.verification_months:
        if month not in by_month or not by_month[month].qualifies:
            return month
    return wallet.verification_months[-1] if wallet.verification_months else wallet.months[-1].month


def what_if_status(view, rules: WalletRules, today: date, *, extra_hours: Decimal, extra_income: Decimal,
                   month: str | None = None) -> ProofKitStatus:
    """MemberView + extra hours/income in one month -> hypothetical ProofKitStatus (view is not modified)."""
    wallet = view.status.wallet
    if wallet is None or (extra_hours <= 0 and extra_income <= 0):
        return view.status
    month = month or target_month(wallet)
    year, mon = map(int, month.split("-"))
    start, end = date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1])
    common = dict(member_id=view.member.member_id, source_doc_id="what-if", period_start=start, period_end=end,
                  source_quote="hypothetical", confidence=1.0)
    extra = []
    if extra_hours > 0:
        extra.append(EarningsRecord(record_id="WHATIF-H", platform="what_if_hours", hours=extra_hours,
                                    gross_income=Decimal("0.00"), **common))
    if extra_income > 0:
        extra.append(EarningsRecord(record_id="WHATIF-I", platform="what_if_income", hours=None,
                                    gross_income=extra_income.quantize(Decimal("0.01")), **common))
    old = {m.month: m for m in wallet.months}
    months = []
    for m in evaluate_months(list(wallet.records) + extra, rules):
        prev = old.get(m.month)  # keep review flags the wallet added outside evaluate_months
        if prev is not None and prev.needs_review and not m.needs_review:
            m = MonthlyCompliance.model_validate({**m.model_dump(), "needs_review": True,
                                                  "review_reasons": prev.review_reasons})
        months.append(m)
    hypo = WalletResult.model_validate({**wallet.model_dump(), "months": [m.model_dump() for m in months]})
    return build_status(view.member, view.status.exemption, hypo, today)
