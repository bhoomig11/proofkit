"""Properties of the month split for statements longer than 31 days, through the text/LLM path.

parse.py: _parse_text -> _records splits any period with (end - start).days > 30 via month_spans + _shares.
The document writes the dates, hours and income, so every record passes grounding and keeps its confidence.

Product decision (Karthik): a statement claiming more than 24 hours a day is never dropped and its hours are
never capped. It is kept with hours None and a confidence below rules.min_record_confidence, so evaluate_months
excludes it and flags every month it touches for review.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from proofkit.contracts import ComplianceBasis, EarningsDocument
from proofkit.wallet import evaluate_months, load_wallet_rules, parse_documents
from tests.unit.wallet.test_parse import llm_one

RULES = load_wallet_rules(Path(__file__).resolve().parents[3] / "config" / "wallet_rules.json")
MEMBER = "SYN-0001"
MAX_HOURS_CENTS = 200_000  # 2000.00


def _cents(lo: int, hi: int):
    return st.integers(lo, hi).map(lambda c: Decimal(c).scaleb(-2))  # exactly 2 decimals: 0.01, 1.00, ...


@st.composite
def statements(draw):
    start = draw(st.dates(date(2027, 1, 1), date(2029, 12, 31)))
    days = draw(st.integers(32, 400))  # inclusive length, always longer than 31 days
    income = draw(_cents(1, 10_000_000))  # 0.01 .. 100000.00
    hours = draw(st.none() | _cents(1, MAX_HOURS_CENTS))  # 0.01 .. 2000.00
    return start, start + timedelta(days=days - 1), income, hours


@st.composite
def over_24_statements(draw):
    """Same ranges, but always more than 24 hours a day, so hypothesis exercises that branch often."""
    start = draw(st.dates(date(2027, 1, 1), date(2029, 12, 31)))
    days = draw(st.integers(32, MAX_HOURS_CENTS // 2400 - 1))  # 32 .. 82: room above 24 * days within 2000.00
    income = draw(_cents(1, 10_000_000))
    hours = draw(_cents(2400 * days + 1, MAX_HOURS_CENTS))
    return start, start + timedelta(days=days - 1), income, hours


INPUTS = statements() | over_24_statements()


def _days(start: date, end: date) -> int:
    return (end - start).days + 1


def _over_24(start: date, end: date, hours: Decimal | None) -> bool:
    return hours is not None and hours > 24 * _days(start, end)


def _parse(start, end, income, hours):
    """A text statement that writes every number and date, plus an LLM that quotes it faithfully."""
    quote = (f"Hours worked: {hours}\n" if hours is not None else "") + f"Earnings: ${income:,}"
    text = f"FreelanceYard statement\nPeriod: {start:%m/%d/%Y} - {end:%m/%d/%Y}\n{quote}\n"
    doc = EarningsDocument(doc_id="t1", member_id=MEMBER, filename="u.txt", doc_type="text", content_text=text)
    llm = llm_one(platform="freelanceyard", period_start=start.isoformat(), period_end=end.isoformat(),
                  hours=None if hours is None else str(hours), gross_income=str(income), source_quote=quote)
    return parse_documents([doc], MEMBER, llm, rules=RULES), quote


def _unsplit_confidence(start: date, income: Decimal) -> float:
    """Confidence the same statement gets when it covers one day and needs no split."""
    recs, _ = _parse(start, start, income, None)
    assert len(recs) == 1
    return recs[0].confidence


# ─────────────────────── every input: kept, split cleanly, income exact ───────────────────────
@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_statement_is_never_dropped(stmt):
    recs, _ = _parse(*stmt)
    assert len(recs) >= 1


@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_every_piece_lies_inside_one_calendar_month(stmt):
    recs, _ = _parse(*stmt)
    assert recs
    assert all((r.period_start.year, r.period_start.month) == (r.period_end.year, r.period_end.month) for r in recs)


@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_pieces_are_contiguous_and_cover_the_whole_period(stmt):
    start, end, *_ = stmt
    recs, _ = _parse(*stmt)
    spans = sorted((r.period_start, r.period_end) for r in recs)
    assert spans and spans[0][0] == start and spans[-1][1] == end
    assert all(s <= e for s, e in spans)
    assert all(nxt[0] == prev[1] + timedelta(days=1) for prev, nxt in zip(spans, spans[1:]))  # no gap, no overlap


@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_every_piece_keeps_the_source_quote(stmt):
    recs, quote = _parse(*stmt)
    assert recs
    assert all(r.source_quote == quote for r in recs)


@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_pieces_are_non_negative_and_sum_exactly_to_source_income(stmt):
    _, _, income, _ = stmt
    recs, _ = _parse(*stmt)
    assert recs
    assert all(r.gross_income >= 0 for r in recs)
    assert sum((r.gross_income for r in recs), Decimal("0")) == income


# ─────────────────────── at most 24 hours a day: hours exact, confidence kept ───────────────────────
@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_plausible_hours_sum_exactly_and_keep_confidence(stmt):
    start, end, income, hours = stmt
    if _over_24(start, end, hours):
        return
    recs, _ = _parse(*stmt)
    assert recs
    if hours is None:
        assert all(r.hours is None for r in recs)
    else:
        assert all(r.hours is not None and r.hours >= 0 for r in recs)
        assert sum((r.hours for r in recs), Decimal("0")) == hours
    expected = _unsplit_confidence(start, income)
    assert all(r.confidence == expected for r in recs)


# ─────────────────────── more than 24 hours a day: kept, flagged, never counted ───────────────────────
@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_over_24_hours_a_day_is_kept_without_hours_and_below_min_confidence(stmt):
    start, end, _, hours = stmt
    if not _over_24(start, end, hours):
        return
    recs, _ = _parse(*stmt)
    assert recs
    assert all(r.hours is None for r in recs)
    assert all(r.confidence < RULES.min_record_confidence for r in recs)


@settings(max_examples=200, deadline=None)
@given(INPUTS)
def test_over_24_hours_a_day_is_excluded_and_every_touched_month_needs_review(stmt):
    start, end, _, hours = stmt
    if not _over_24(start, end, hours):
        return
    recs, _ = _parse(*stmt)
    assert recs
    ids = {r.record_id for r in recs}
    touched = {r.period_start.strftime("%Y-%m") for r in recs}
    months = {m.month: m for m in evaluate_months(recs, RULES)}
    assert touched <= months.keys()
    for month in touched:
        m = months[month]
        assert not ids & set(m.record_ids)  # excluded: none of them count
        assert m.needs_review is True
        assert m.review_reasons
        assert m.basis != ComplianceBasis.HOURS


# ─────────────────────── examples ───────────────────────
def test_statement_over_24_hours_a_day_is_flagged_not_dropped():
    recs, _ = _parse(date(2027, 1, 1), date(2027, 2, 1), Decimal("0.01"), Decimal("768.01"))
    assert recs
    months = {m.month: m for m in evaluate_months(recs, RULES)}
    for month in ("2027-01", "2027-02"):
        assert month in months
        assert months[month].needs_review is True
        assert months[month].review_reasons


def test_tiny_amount_split_never_goes_negative():
    recs, _ = _parse(date(2027, 1, 1), date(2027, 4, 1), Decimal("0.02"), None)
    assert recs
    assert all(r.gross_income >= Decimal("0.00") for r in recs)
    assert sum((r.gross_income for r in recs), Decimal("0")) == Decimal("0.02")
