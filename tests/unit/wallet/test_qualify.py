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


def stmt(rid, doc, start, end, hours, platform="doordash"):
    return EarningsRecord(record_id=rid, member_id="SYN-0001", source_doc_id=doc, platform=platform,
                          period_start=start, period_end=end, hours=D(hours), gross_income=D(hours) * 10,
                          source_quote="q", confidence=0.95)


def test_overlapping_statements_from_different_docs_are_not_double_counted(rules):
    monthly = stmt("m", "d1", date(2027, 2, 1), date(2027, 2, 28), "80")
    weekly = stmt("w", "d2", date(2027, 2, 1), date(2027, 2, 7), "20")  # same days, uploaded again as a weekly
    m = evaluate_months([monthly, weekly], rules)[0]
    assert m.total_hours == D("0.00") and not m.qualifies
    assert m.needs_review and any("overlap" in r for r in m.review_reasons)


@pytest.mark.parametrize("records", [
    [stmt("a", "d1", date(2027, 2, 1), date(2027, 2, 28), "40"),
     stmt("b", "d2", date(2027, 2, 1), date(2027, 2, 28), "40", platform="uber")],  # two platforms at once is normal
    [stmt("a", "d1", date(2027, 2, 1), date(2027, 2, 14), "40"),
     stmt("b", "d2", date(2027, 2, 15), date(2027, 2, 28), "40")],                  # back to back, no overlap
])
def test_non_overlapping_or_other_platform_records_both_count(rules, records):
    m = evaluate_months(records, rules)[0]
    assert m.total_hours == D("80.00") and not m.needs_review


def test_averaging_flag_cannot_be_turned_on_until_implemented(wallet_rules_path, tmp_path):
    """Otherwise setting it true would be silently ignored and members would get the wrong basis."""
    import json
    cfg = json.loads(wallet_rules_path.read_text())
    cfg["allow_seasonal_income_averaging"]["value"] = True
    p = tmp_path / "w.json"
    p.write_text(json.dumps(cfg))
    with pytest.raises(ValueError, match="averaging"):
        load_wallet_rules(p)


def test_monthly_total_and_weekly_line_in_one_doc_are_not_double_counted(rules):
    monthly = stmt("m", "d1", date(2027, 2, 1), date(2027, 2, 28), "80")
    weekly = stmt("w", "d1", date(2027, 2, 1), date(2027, 2, 7), "20")  # same doc lists the week and the month
    m = evaluate_months([monthly, weekly], rules)[0]
    assert m.total_hours == D("0.00") and m.needs_review
