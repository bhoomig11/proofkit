"""
P2 owns this. Untrusted documents -> EarningsRecord[].

- CSV: parse deterministically with the csv module (no LLM).
- TEXT: LLM task="extract_earnings", returning {"records": [{"platform","period_start","period_end","hours","gross_income","source_quote","confidence"}]}
- PDF: extract text (pypdf, page cap from rules), then the same as TEXT.
- IMAGE: stretch goal. For now return no records for it; the evaluate step flags the month for review.
Every LLM record must pass: the source_quote is found in the document, it doesn't overlap injection_spans,
the numbers in the record appear in the source_quote, and it validates against the contract.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from proofkit.common.llm import LLMClient
from proofkit.common.redact import get_logger
from proofkit.contracts import DocumentType, EarningsDocument, EarningsRecord
from proofkit.wallet.rules import WalletRules, load_wallet_rules
from proofkit.wallet.tokens import parse_hours, parse_money

LLM_TASK = "extract_earnings"
DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "wallet_rules.json"
CSV_CONFIDENCE = 1.0
UNKNOWN_PLATFORM_CONFIDENCE = 0.5  # below min_record_confidence: kept for the audit trail, excluded and flagged
_CSV_COLUMNS = {
    "platform": ("platform",),
    "period_start": ("period_start",),
    "period_end": ("period_end",),
    "hours": ("hours",),
    "income": ("gross_pay", "gross_income", "earnings", "total"),
}
log = get_logger(__name__)


def parse_documents(docs: list[EarningsDocument], member_id: str, llm: LLMClient, *,
                    rules: WalletRules | None = None) -> list[EarningsRecord]:
    """EarningsDocument[] -> EarningsRecord[]. `rules` defaults to config/wallet_rules.json."""
    rules = rules or load_wallet_rules(DEFAULT_RULES_PATH)
    out: list[EarningsRecord] = []
    for d in docs:
        if d.doc_type == DocumentType.CSV:
            recs = _parse_csv(d, member_id, rules)
        else:
            raise NotImplementedError(d.doc_type)
        log.info("parsed doc_id=%s type=%s records=%d", d.doc_id, d.doc_type.value, len(recs))
        out += recs
    return out


def _record(doc: EarningsDocument, member_id: str, i: int, rules: WalletRules, *, platform: str, start: date,
            end: date, hours: Decimal | None, income: Decimal, quote: str, confidence: float) -> EarningsRecord | None:
    if platform not in rules.known_platforms:
        confidence = min(confidence, UNKNOWN_PLATFORM_CONFIDENCE)
    try:
        return EarningsRecord(record_id=f"R-{doc.doc_id}-{i}", member_id=member_id, source_doc_id=doc.doc_id,
                              platform=platform, period_start=start, period_end=end, hours=hours,
                              gross_income=income, source_quote=quote, confidence=confidence)
    except ValidationError:
        return None


def _parse_csv(doc: EarningsDocument, member_id: str, rules: WalletRules) -> list[EarningsRecord]:
    # Row by row on raw lines, so each record's source_quote is the exact line it came from.
    # ponytail: a row longer than 31 days is dropped, not split by month; split it when real exports need that.
    lines = (doc.content_text or "").splitlines()
    try:
        header = [h.strip().lower() for h in next(csv.reader(lines[:1]), [])]
    except csv.Error:
        return []
    col = {key: header.index(n) for key, names in _CSV_COLUMNS.items() for n in reversed(names) if n in header}
    if not {"platform", "period_start", "period_end", "income"} <= col.keys():
        return []

    out: list[EarningsRecord] = []
    for line in lines[1:]:
        try:
            row = next(csv.reader([line]), [])
        except csv.Error:
            continue
        if len(row) != len(header):
            continue
        platform = row[col["platform"]].strip().lower()
        income = parse_money(row[col["income"]])
        hours_cell = row[col["hours"]].strip() if "hours" in col else ""
        hours = parse_hours(hours_cell) if hours_cell else None
        try:
            start = date.fromisoformat(row[col["period_start"]].strip())
            end = date.fromisoformat(row[col["period_end"]].strip())
        except ValueError:
            continue
        if not platform or income is None or income < 0 or (hours_cell and hours is None):
            continue
        rec = _record(doc, member_id, len(out), rules, platform=platform, start=start, end=end, hours=hours,
                      income=income, quote=line, confidence=CSV_CONFIDENCE)
        if rec:
            out.append(rec)
    return out
