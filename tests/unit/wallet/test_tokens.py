from decimal import Decimal as D

import pytest

from proofkit.wallet.tokens import hours_in, money_in, parse_hours, parse_money


@pytest.mark.parametrize("cell, want", [
    ("$1,480.00", "1480.00"),
    ("1,480.00 USD", "1480.00"),
    ("USD 1,480.00", "1480.00"),
    ("1480", "1480"),
    ("$0.99", "0.99"),
    ("-$25.00", "-25.00"),   # negative adjustment: parsed, never matches a gross_income (contract is >= 0)
    ("-25.00", "-25.00"),
    (" 298.10 ", "298.10"),
    ("", None),
    ("abc", None),
    ("1,48", None),          # bad thousands grouping
    ("12.345", None),        # sub-cent precision is not money
    ("1e3", None),
    ("NaN", None),
])
def test_parse_money(cell, want):
    assert parse_money(cell) == (None if want is None else D(want))


@pytest.mark.parametrize("text, want", [
    ("Gross fares 1,480.00 USD\nTips 112.00 USD", ["1480.00", "112.00"]),
    ("Total earnings: $410.00", ["410.00"]),
    ("USD 1,480.00", ["1480.00"]),
    ("Adjustment: -$25.00", ["-25.00"]),
    ("Fixed-price milestone paid 02/14/2027: $180.00", ["180.00"]),  # the date is not money
    ("Online hours 92.5", []),                                       # unmarked numbers are not money
    ("Tasks completed: 7 | Hours invoiced: 18", []),
])
def test_money_in_text_needs_a_currency_marker(text, want):
    assert money_in(text) == [D(w) for w in want]


@pytest.mark.parametrize("cell, want", [
    ("22", "22"), ("24.5", "24.5"), ("49 hr 30 min", "49.50"), ("", None), ("x", None), ("-3", None),
])
def test_parse_hours(cell, want):
    assert parse_hours(cell) == (None if want is None else D(want))


@pytest.mark.parametrize("text, want", [
    ("Active time: 49 hr 30 min", ["49.50"]),
    ("1h 15m", ["1.25"]),
    ("92.5 hrs", ["92.50"]),
    ("Hours invoiced: 18", ["18.00"]),
    ("Online hours 92.5", ["92.50"]),
    ("Active time: 30 hr 0 min", ["30.00"]),
    ("1 hr 20 min", ["1.33"]),                              # rounded half-up to 0.01 h
    ("Tasks completed: 7 | Hours invoiced: 18", ["18.00"]),  # the task count is not hours
    ("Total earnings: $410.00", []),
    ("paid 02/14/2027", []),
    ("5 hr 75 min", []),                                    # impossible minutes: not a token
])
def test_hours_in_text(text, want):
    assert hours_in(text) == [D(w) for w in want]
