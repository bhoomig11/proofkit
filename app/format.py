"""Pure display formatting helpers for Coverage Copilot."""
from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

_CENTS = Decimal("0.01")


def format_money(value: Decimal) -> str:
    """Format a Decimal currency value with half-up rounding and two places."""
    if not isinstance(value, Decimal):
        raise TypeError("money values must be Decimal")
    return f"${value.quantize(_CENTS, rounding=ROUND_HALF_UP):,.2f}"


def long_date(value: date) -> str:
    """Format a date without platform-specific zero-padding directives."""
    return f"{value:%B} {value.day}, {value.year}"


def countdown(today: date, due: date) -> str:
    """Return a plain-language proof deadline countdown."""
    days = (due - today).days
    if days == 0:
        return "Proof due today"
    if days > 0:
        return f"Proof due in {days} {'day' if days == 1 else 'days'}"
    overdue = abs(days)
    return f"Proof was due {overdue} {'day' if overdue == 1 else 'days'} ago"


def month_long(month: str) -> str:
    """Convert YYYY-MM to a long month label."""
    try:
        year_text, month_text = month.split("-")
        year, number = int(year_text), int(month_text)
        if not 1 <= number <= 12:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("month must be YYYY-MM") from exc
    return f"{calendar.month_name[number]} {year}"


def plain_protected_by(value: str | None) -> str | None:
    """Turn the backend's protected_by code into member-friendly copy."""
    if value is None:
        return None
    labels = {
        "exemption:medically_frail": "Medical frailty exemption",
        "exemption:substance_use_treatment": "Substance use treatment exemption",
        "exemption:disability": "Disability exemption",
        "compliance:hours": "80+ hours this month",
        "compliance:income": "$580+ income this month",
        "compliance:averaged_income": "Average income requirement",
    }
    return labels.get(value, value.replace(":", ": ").replace("_", " ").capitalize())
