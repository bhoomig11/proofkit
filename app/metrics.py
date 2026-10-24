"""RenewRight UI extra: three metric tiles (hours, income, proof deadline) for one member.

Thresholds come from ``WalletRules`` (default: config/wallet_rules.json). Pure helpers; Streamlit
is imported only inside ``render_metric_tiles``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Optional

from app.format import countdown, format_money, month_long
from proofkit.contracts import MonthlyCompliance, ProofKitStatus
from proofkit.wallet import WalletRules, load_wallet_rules

__all__ = ["Tile", "metric_tiles", "render_metric_tiles"]

DEFAULT_WALLET_RULES = Path(__file__).resolve().parents[1] / "config" / "wallet_rules.json"
NA = "n/a"
_CENT = Decimal("0.01")


@dataclass(frozen=True)
class Tile:
    """One st.metric tile."""

    label: str
    value: str
    delta: Optional[str]
    help: str


def _hours(value: Decimal) -> str:
    return f"{value.quantize(_CENT, rounding=ROUND_HALF_UP):.2f}"


def _plain(value: Decimal) -> str:
    """80 -> '80', 80.5 -> '80.50' (a threshold shown without needless decimals)."""
    return f"{value:.0f}" if value == value.to_integral_value() else _hours(value)


def _focus_month(status: ProofKitStatus) -> Optional[MonthlyCompliance]:
    """First failing verification month, else the first verification month present in wallet.months."""
    if status.wallet is None:
        return None
    by_month = {m.month: m for m in status.wallet.months}
    present = [by_month[m] for m in status.wallet.verification_months if m in by_month]
    failing = [m for m in present if not m.qualifies]
    return (failing or present or [None])[0]


def metric_tiles(status: ProofKitStatus, today: date, rules: Optional[WalletRules] = None) -> list[Tile]:
    """Build [hours, income, deadline] tiles from a ``ProofKitStatus``. Missing data shows "n/a"."""
    rules = rules if rules is not None else load_wallet_rules(DEFAULT_WALLET_RULES)
    hours_req, income_req = rules.monthly_hours_required, rules.monthly_income_required
    month = _focus_month(status)
    when = f" in {month_long(month.month)}" if month is not None else ""

    hours_help = f"Hours of work, school or community service{when}. The rule is {_plain(hours_req)} h a month."
    income_help = f"Gross income{when}. The rule is {format_money(income_req)} a month."
    deadline_help = "The date your proof is due, a few days before your renewal."

    if month is None:
        hours = Tile("Hours this month", NA, None, hours_help)
        income = Tile("Income this month", NA, None, income_help)
    else:
        hours = Tile(
            "Hours this month",
            f"{_hours(month.total_hours)} / {_plain(hours_req)} h",
            f"-{_hours(month.shortfall_hours)} h" if month.shortfall_hours > 0 else "met",
            hours_help,
        )
        income = Tile(
            "Income this month",
            f"{format_money(month.total_income)} / {format_money(income_req)}",
            f"-{format_money(month.shortfall_income)}" if month.shortfall_income > 0 else "met",
            income_help,
        )

    if status.wallet is None:
        deadline = Tile("Proof deadline", NA, None, deadline_help)
    else:
        due = status.wallet.proof_due_date
        deadline = Tile("Proof deadline", countdown(today, due), None, f"{deadline_help} Due {due.isoformat()}.")
    return [hours, income, deadline]


def render_metric_tiles(status: ProofKitStatus, today: date, rules: Optional[WalletRules] = None) -> None:
    """Render the three tiles from ``metric_tiles`` in ``st.columns(3)`` with ``st.metric``."""
    import streamlit as st

    for col, tile in zip(st.columns(3), metric_tiles(status, today, rules), strict=False):
        with col:
            st.metric(tile.label, tile.value, tile.delta, help=tile.help)
