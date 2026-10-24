from datetime import date
from decimal import Decimal as D

import pytest

from proofkit.common.llm import FakeLLM, LLMError
from proofkit.contracts import EarningsDocument
from proofkit.wallet import load_wallet_rules, parse_documents


@pytest.fixture
def rules(wallet_rules_path):
    return load_wallet_rules(wallet_rules_path)


def csv_doc(text, doc_id="c1"):
    return EarningsDocument(doc_id=doc_id, member_id="SYN-0001", filename="x.csv", doc_type="csv", content_text=text)


def test_csv_aliases_ids_and_quotes(rules):
    text = ("Platform , Period_Start,Period_End,Hours,Earnings\n"
            "DoorDash,2027-02-01,2027-02-07,10,$120.50\n"
            "upwork,2027-02-08,2027-02-14,,1,200.00 USD\n")  # unquoted comma: wrong column count, dropped
    text2 = "platform,period_start,period_end,hours,total\nupwork,2027-02-08,2027-02-14,,\"1,200.00\"\n"
    out = parse_documents([csv_doc(text), csv_doc(text2, "c2")], "SYN-0001", FakeLLM({}), rules=rules)
    assert [(r.record_id, r.platform, r.hours, r.gross_income) for r in out] == [
        ("R-c1-0", "doordash", D("10"), D("120.50")),
        ("R-c2-0", "upwork", None, D("1200.00")),
    ]
    assert out[0].source_quote == "DoorDash,2027-02-01,2027-02-07,10,$120.50"
    assert out[1].period_start == date(2027, 2, 8)


@pytest.mark.parametrize("row", [
    "doordash,02/01/2027,2027-02-07,10,100.00",   # non-ISO date
    "doordash,2027-02-07,2027-02-01,10,100.00",   # end before start
    "doordash,2027-01-01,2027-03-01,10,100.00",   # longer than 31 days
    "doordash,2027-02-01,2027-02-07,10,abc",      # income not money
    "doordash,2027-02-01,2027-02-07,10,-25.00",   # negative adjustment is not earnings
    "doordash,2027-02-01,2027-02-07,-4,100.00",   # negative hours
    "doordash,2027-02-01,2027-02-07,10",          # missing column
    ",2027-02-01,2027-02-07,10,100.00",           # no platform
    "doordash,2027-02-01,2027-02-07,10,100.00," + "x" * 600,  # too long to be a source_quote
])
def test_bad_csv_rows_are_dropped_not_guessed(rules, row):
    text = f"platform,period_start,period_end,hours,gross_pay\n{row}\n"
    assert parse_documents([csv_doc(text)], "SYN-0001", FakeLLM({}), rules=rules) == []


def test_csv_without_income_column_gives_nothing(rules):
    text = "platform,period_start,period_end,hours\ndoordash,2027-02-01,2027-02-07,10\n"
    assert parse_documents([csv_doc(text)], "SYN-0001", FakeLLM({}), rules=rules) == []


def test_unknown_platform_kept_with_confidence_below_threshold(rules):
    text = "platform,period_start,period_end,hours,gross_pay\nShadyGigs,2027-02-01,2027-02-07,10,100.00\n"
    (r,) = parse_documents([csv_doc(text)], "SYN-0001", FakeLLM({}), rules=rules)
    assert r.platform == "shadygigs" and r.confidence < rules.min_record_confidence


def text_doc(text="Uber Feb 2027\nOnline hours 92.5\nGross fares 1,480.00 USD\n"):
    return EarningsDocument(doc_id="t1", member_id="SYN-0001", filename="u.txt", doc_type="text", content_text=text)


def _fail(instructions, untrusted):
    raise LLMError("bad json")


@pytest.mark.parametrize("response", [
    _fail,
    ["not", "a", "dict"],
    {"records": "nope"},
    {"records": ["nope", 3, None]},
    {"records": [{"platform": "uber"}]},  # missing fields
    {"records": [{"platform": ["uber"], "period_start": "2027-02-01", "period_end": "2027-02-28", "hours": "92.5",
                  "gross_income": "1480.00", "source_quote": "Online hours 92.5", "confidence": "high"}]},
])
def test_llm_failure_or_garbage_gives_no_records(rules, response):
    assert parse_documents([text_doc()], "SYN-0001", FakeLLM({"extract_earnings": response}), rules=rules) == []
