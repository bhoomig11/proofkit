from datetime import date
from decimal import Decimal as D

import pytest

from proofkit.contracts import EarningsRecord
from proofkit.wallet import evaluate_months, load_wallet_rules


@pytest.fixture
def rules(wallet_rules_path):
    return load_wallet_rules(wallet_rules_path)


def rec(start, end, hours="3", income="30.00", rid="r1"):
    return EarningsRecord(record_id=rid, member_id="SYN-0001", source_doc_id="d1", platform="doordash",
                          period_start=start, period_end=end, hours=D(hours), gross_income=D(income),
                          source_quote="q", confidence=0.95)


@pytest.mark.parametrize("start, end, feb, mar", [
    (date(2028, 2, 28), date(2028, 3, 1), ("2.00", "20.00"), ("1.00", "10.00")),  # leap: Feb 28, 29 | Mar 1
    (date(2027, 2, 28), date(2027, 3, 2), ("1.00", "10.00"), ("2.00", "20.00")),  # non-leap: Feb 28 | Mar 1, 2
])
def test_february_proration_respects_leap_years(rules, start, end, feb, mar):
    months = {m.month: m for m in evaluate_months([rec(start, end)], rules)}
    y = start.year
    assert (months[f"{y}-02"].total_hours, months[f"{y}-02"].total_income) == (D(feb[0]), D(feb[1]))
    assert (months[f"{y}-03"].total_hours, months[f"{y}-03"].total_income) == (D(mar[0]), D(mar[1]))


def dup(rid, doc, conf=0.95):
    return EarningsRecord(record_id=rid, member_id="SYN-0001", source_doc_id=doc, platform="doordash",
                          period_start=date(2027, 2, 1), period_end=date(2027, 2, 7), hours=D("10"),
                          gross_income=D("100.00"), source_quote="q", confidence=conf)


@pytest.mark.parametrize("records, hours", [
    ([dup("r1", "d1"), dup("r2", "d1")], "20.00"),            # same doc: two real gigs, both count
    ([dup("r1", "d1", conf=0.3), dup("r2", "d2")], "10.00"),  # low-confidence copy never suppresses the good one
])
def test_dedupe_only_across_docs_and_after_confidence_filter(rules, records, hours):
    assert evaluate_months(records, rules)[0].total_hours == D(hours)
