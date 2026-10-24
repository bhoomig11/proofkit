"""FINAL: member-facing SMS reminder built from a ProofKitStatus.

Pure function of its arguments: no clock, no randomness, no I/O, no LLM, no logging.
Only the folded first name, dates, money and fixed template text ever enter the message (R4).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Optional

from proofkit.contracts import Member, OverallStatus, ProofKitStatus

__all__ = ["sms_reminder"]

SMS_LIMIT = 160
_FIRST_NAME_MAX = 20
_FALLBACK_NAME = "there"
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")
_NAME_SHAPE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_PROGRAM_NAMES = frozenset({"masshealth", "medicaid"})
_CENT = Decimal("0.01")

# (text, required) pairs; optional clauses are dropped first when the message is too long.
Clause = tuple[str, bool]


def _first_name(display_name: str) -> str:
    """R3: drop one trailing '(...)' suffix, take the first token, NFKD-fold to ASCII, cut to 20.

    The result is used only if it is name-shaped (a letter, then letters, apostrophes or hyphens)
    and is not a program name; otherwise the generic greeting 'there' is used.
    """
    tokens = _SUFFIX.sub("", display_name).split()
    if not tokens:
        return _FALLBACK_NAME
    folded = "".join(c for c in unicodedata.normalize("NFKD", tokens[0]) if c.isascii())[:_FIRST_NAME_MAX]
    if _NAME_SHAPE.fullmatch(folded) is None or folded.lower() in _PROGRAM_NAMES:
        return _FALLBACK_NAME
    return folded


def _fmt_date(d: date) -> str:
    """R7: 'Mar 6, 2027', locale-free, no zero padding."""
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"


def _fmt_month(month: str) -> str:
    """'2027-02' -> 'Feb 2027'."""
    year, mon = month.split("-")
    return f"{_MONTHS[int(mon) - 1]} {year}"


def _fmt_money(x: Decimal) -> str:
    """R7: '$60.00', independent of the caller's decimal context (fixed precision, half-up)."""
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        return f"${x.quantize(_CENT):.2f}"


def _check_member_ids(member: Member, status: ProofKitStatus) -> None:
    """Raise ValueError if any id in ``status`` differs from ``member.member_id``; names fields only."""
    mismatched = []
    if status.member_id != member.member_id:
        mismatched.append("status.member_id")
    if status.wallet is not None and status.wallet.member_id != member.member_id:
        mismatched.append("status.wallet.member_id")
    if status.exemption is not None and status.exemption.member_id != member.member_id:
        mismatched.append("status.exemption.member_id")
    if mismatched:
        raise ValueError(f"member_id mismatch: {', '.join(mismatched)} differs from member.member_id")


def _due(status: ProofKitStatus) -> Optional[date]:
    """R5: next_deadline, else wallet.proof_due_date, else unknown."""
    if status.next_deadline is not None:
        return status.next_deadline
    return status.wallet.proof_due_date if status.wallet is not None else None


def _renewal(member: Member, status: ProofKitStatus) -> date:
    """R5: wallet.next_renewal_date, else member.renewal_date."""
    return status.wallet.next_renewal_date if status.wallet is not None else member.renewal_date


def _shortfall(status: ProofKitStatus) -> Optional[tuple[str, Decimal]]:
    """R5: (month, income shortfall) of the first verification month present in wallet.months that fails."""
    if status.wallet is None:
        return None
    by_month = {m.month: m for m in status.wallet.months}
    for month in status.wallet.verification_months:
        mc = by_month.get(month)
        if mc is not None and not mc.qualifies:
            return month, mc.shortfall_income
    return None


def _by_due(due: Optional[date]) -> str:
    return f" by {_fmt_date(due)}." if due is not None else "."


def _clauses(member: Member, status: ProofKitStatus) -> list[Clause]:
    """R5: fixed template clauses for the member's overall status."""
    if status.status == OverallStatus.PROTECTED:
        return [
            (" you're on track.", True),
            (" No action needed now.", True),
            (f" Next renewal: {_fmt_date(_renewal(member, status))}.", True),
            (" -ProofKit", False),
        ]
    due = _due(status)
    if status.status == OverallStatus.NEEDS_REVIEW:
        return [
            (" Part of your proof needs a review.", True),
            (" Contact your navigator or clinic" + _by_due(due), True),
        ]
    short = _shortfall(status)
    if short is None:
        return [
            (" We still need proof of your work hours or income.", True),
            (" Send pay stubs or volunteer hours" + _by_due(due), True),
        ]
    month, amount = short
    return [
        (f" You're {_fmt_money(amount)} short for {_fmt_month(month)}.", True),
        (" Send pay stubs or volunteer hours" + _by_due(due), True),
        (" Reply STOP to opt out.", False),
    ]


def _fit(greeting: str, clauses: list[Clause]) -> str:
    """R1: drop optional clauses from the end first; as a last resort cut at a word boundary."""
    kept = list(clauses)
    msg = greeting + "".join(text for text, _ in kept)
    while len(msg) > SMS_LIMIT:
        optional = [i for i, (_, required) in enumerate(kept) if not required]
        if not optional:
            break
        del kept[optional[-1]]
        msg = greeting + "".join(text for text, _ in kept)
    if len(msg) > SMS_LIMIT:
        cut = msg.rfind(" ", 0, SMS_LIMIT + 1)
        msg = msg[:cut] if cut > 0 else msg[:SMS_LIMIT]
    return msg


def sms_reminder(member: Member, status: ProofKitStatus) -> str:
    """Build one SMS (<= 160 printable ASCII chars) for a member.

    Takes the contract models ``Member`` and ``ProofKitStatus`` and returns a plain ``str``.
    Reads only the display name's first token, status, dates and the first failing verification
    month's income shortfall; never ids, phone digits, exemption details, findings or action text.
    Raises ``ValueError`` before rendering if the status, wallet or exemption belongs to another member.
    """
    _check_member_ids(member, status)
    greeting = f"Hi {_first_name(member.display_name)},"
    msg = _fit(greeting, _clauses(member, status))
    assert all(" " <= c <= "~" for c in msg)
    return msg
