"""P2 owns this. Money and hours tokens found in untrusted text. Pure, Decimal only."""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?"
_END = r"(?![\d.,]\d)"  # don't stop in the middle of a longer number
_MONEY_CELL = re.compile(rf"\s*(-)?\s*(?:\$|USD\s*)?({_NUM})\s*(?:USD)?\s*", re.I)
# Money in free text needs a currency marker, so dates, counts and hours are never read as income.
_MONEY_TEXT = re.compile(
    rf"(-)?\$\s?({_NUM}){_END}"
    rf"|(?<![\d.,])(-)?({_NUM})\s?USD\b"
    rf"|\bUSD\s?(-)?({_NUM}){_END}",
    re.I,
)
_HOURS_TEXT = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:hours|hour|hrs|hr|h)\b"                 # 92.5 hrs, 49 hr [30 min], 1h [15m]
    r"(?:\s*(\d{1,2})\s*(?:minutes|minute|mins|min|m)\b)?"
    r"|\bhours?\b(?:\s+[a-z]+)?\s*:?\s*(\d+(?:\.\d+)?)(?![\d.])",            # Online hours 92.5, Hours invoiced: 18
    re.I,
)
_PLAIN_HOURS = re.compile(r"\s*(\d+(?:\.\d+)?)\s*")
CENT = Decimal("0.01")


def _money(sign: str | None, num: str) -> Decimal:
    value = Decimal(num.replace(",", ""))
    return -value if sign else value


def parse_money(cell: str) -> Decimal | None:
    """One cell or token -> Decimal (negative for adjustments), or None if it isn't money."""
    m = _MONEY_CELL.fullmatch(cell)
    return _money(m[1], m[2]) if m else None


def money_in(text: str) -> list[Decimal]:
    """Currency-marked amounts ($410.00, 1,480.00 USD, USD 1,480.00) in text, in order."""
    out = []
    for m in _MONEY_TEXT.finditer(text):
        sign, num = next((m[i], m[i + 1]) for i in (1, 3, 5) if m[i + 1])
        out.append(_money(sign, num))
    return out


def hours_in(text: str) -> list[Decimal]:
    """Hours tokens in text, rounded half-up to 0.01 h. '49 hr 30 min' -> 49.50."""
    out = []
    for m in _HOURS_TEXT.finditer(text):
        if m[3]:
            out.append(Decimal(m[3]).quantize(CENT, ROUND_HALF_UP))
            continue
        minutes = Decimal(m[2] or 0)
        if minutes < 60:
            out.append((Decimal(m[1]) + minutes / 60).quantize(CENT, ROUND_HALF_UP))
    return out


def parse_hours(cell: str) -> Decimal | None:
    """One cell -> hours. A bare non-negative number, or exactly one hours token."""
    if m := _PLAIN_HOURS.fullmatch(cell):
        return Decimal(m[1])
    found = hours_in(cell)
    return found[0] if len(found) == 1 else None
