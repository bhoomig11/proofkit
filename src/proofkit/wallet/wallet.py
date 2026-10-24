"""P2 owns this. Glue: parse -> evaluate -> deadlines -> WalletResult."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from proofkit.common.llm import LLMClient
from proofkit.contracts import ComplianceBasis, DocumentType, EarningsDocument, Member, MonthlyCompliance, WalletResult
from proofkit.wallet.deadlines import compute_deadlines
from proofkit.wallet.parse import parse_documents
from proofkit.wallet.qualify import evaluate_months
from proofkit.wallet.rules import WalletRules


def build_wallet(member: Member, docs: list[EarningsDocument], llm: LLMClient, rules: WalletRules, today: date) -> WalletResult:
    """Member + EarningsDocument[] -> WalletResult. Rejected uploads raise ValueError. `today` is unused for now."""
    records = parse_documents(docs, member.member_id, llm, rules=rules)
    months = {m.month: m for m in evaluate_months(records, rules)}
    verification_months, proof_due = compute_deadlines(member, rules)

    images = [d.doc_id for d in docs if d.doc_type == DocumentType.IMAGE]
    if images:  # we can't read images yet, so the months that matter need a human look
        reason = f"image upload(s) {', '.join(images)} not read; check them by hand"
        for month in verification_months:
            m = months.get(month) or _empty_month(month, rules)
            months[month] = m.model_copy(update={"needs_review": True, "review_reasons": [*m.review_reasons, reason]})

    return WalletResult(member_id=member.member_id, records=records, months=sorted(months.values(), key=lambda m: m.month),
                        verification_months=verification_months, next_renewal_date=member.renewal_date,
                        proof_due_date=proof_due, rules_version=rules.rules_version)


def _empty_month(month: str, rules: WalletRules) -> MonthlyCompliance:
    zero = Decimal("0.00")
    return MonthlyCompliance(month=month, total_hours=zero, hours_known_for_all_records=True, total_income=zero,
                             qualifies=False, basis=ComplianceBasis.NONE,
                             shortfall_hours=rules.monthly_hours_required.quantize(zero),
                             shortfall_income=rules.monthly_income_required.quantize(zero), record_ids=[])
