"""P2 owns this. Money and hours tokens found in untrusted text. Pure, Decimal only."""
from __future__ import annotations

from decimal import Decimal


def parse_money(cell: str) -> Decimal | None:
    raise NotImplementedError


def money_in(text: str) -> list[Decimal]:
    raise NotImplementedError


def parse_hours(cell: str) -> Decimal | None:
    raise NotImplementedError


def hours_in(text: str) -> list[Decimal]:
    raise NotImplementedError
