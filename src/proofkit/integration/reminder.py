"""FINAL: member-facing SMS reminder built from a ProofKitStatus.

Pure function of its arguments: no clock, no randomness, no I/O, no LLM, no logging.
Only the folded first name, dates, money and fixed template text ever enter the message (R4).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import NamedTuple, Optional

from proofkit.contracts import Member, OverallStatus, ProofKitStatus

__all__ = ["sms_reminder"]

SMS_LIMIT = 160
_FIRST_NAME_MAX = 20
_FALLBACK_NAME = "there"
_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")
_NAME_SHAPE = re.compile(r"[A-Za-z][A-Za-z'-]*")
_PROGRAM_NAMES = frozenset({"masshealth", "medicaid"})
_CENT = Decimal("0.01")

# (text, required) pairs; optional clauses are dropped first when the message is too long.
Clause = tuple[str, bool]


class _Templates(NamedTuple):
    """Fixed, ASCII-only wording for one language. ``{...}`` slots take only dates and money."""

    greeting: str
    months: tuple[str, ...]
    date_fmt: str  # slots: {mon}, {day}, {year}
    by_due: str  # slot: {date}; used when a deadline is known
    on_track: str
    no_action: str
    next_renewal: str  # slot: {date}
    signature: str
    review: str
    contact: str
    need_proof: str
    send_proof: str
    short: str  # slots: {amount}, {month}
    stop: str


_TEMPLATES: dict[str, _Templates] = {
    "en": _Templates(
        greeting="Hi {name},",
        months=("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
        date_fmt="{mon} {day}, {year}",
        by_due=" by {date}.",
        on_track=" you're on track.",
        no_action=" No action needed now.",
        next_renewal=" Next renewal: {date}.",
        signature=" -ProofKit",
        review=" Part of your proof needs a review.",
        contact=" Contact your navigator or clinic",
        need_proof=" We still need proof of your work hours or income.",
        send_proof=" Send pay stubs or volunteer hours",
        short=" You're {amount} short for {month}.",
        stop=" Reply STOP to opt out.",
    ),
    "es": _Templates(
        greeting="Hola {name},",
        months=("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
        date_fmt="{day} {mon} {year}",
        by_due=" antes del {date}.",
        on_track=" vas bien.",
        no_action=" No necesitas hacer nada ahora.",
        next_renewal=" Proxima renovacion: {date}.",
        signature=" -ProofKit",
        review=" Parte de tu prueba necesita revision.",
        contact=" Contacta a tu navegador o clinica",
        need_proof=" Aun necesitamos prueba de tus horas de trabajo o ingresos.",
        send_proof=" Envia talones de pago u horas de voluntariado",
        short=" Te faltan {amount} para {month}.",
        stop=" Responde STOP para cancelar.",
    ),
    "pt": _Templates(
        greeting="Ola {name},",
        months=("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"),
        date_fmt="{day} {mon} {year}",
        by_due=" ate {date}.",
        on_track=" voce esta em dia.",
        no_action=" Nenhuma acao necessaria agora.",
        next_renewal=" Proxima renovacao: {date}.",
        signature=" -ProofKit",
        review=" Parte da sua prova precisa de revisao.",
        contact=" Fale com seu navegador ou clinica",
        need_proof=" Ainda precisamos de prova das suas horas de trabalho ou renda.",
        send_proof=" Envie holerites ou horas de voluntariado",
        short=" Faltam {amount} para {month}.",
        stop=" Responda STOP para sair.",
    ),
}


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


def _fmt_date(d: date, t: _Templates) -> str:
    """R7: locale-free, no zero padding ('Mar 6, 2027' in en, '6 mar 2027' in es/pt)."""
    return t.date_fmt.format(mon=t.months[d.month - 1], day=d.day, year=d.year)


def _fmt_month(month: str, t: _Templates) -> str:
    """'2027-02' -> 'Feb 2027' (en) / 'feb 2027' (es) / 'fev 2027' (pt)."""
    year, mon = month.split("-")
    return f"{t.months[int(mon) - 1]} {year}"


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


def _by_due(due: Optional[date], t: _Templates) -> str:
    return t.by_due.format(date=_fmt_date(due, t)) if due is not None else "."


def _clauses(member: Member, status: ProofKitStatus, t: _Templates) -> list[Clause]:
    """R5: fixed template clauses for the member's overall status, in language ``t``."""
    if status.status == OverallStatus.PROTECTED:
        return [
            (t.on_track, True),
            (t.no_action, True),
            (t.next_renewal.format(date=_fmt_date(_renewal(member, status), t)), True),
            (t.signature, False),
        ]
    due = _due(status)
    if status.status == OverallStatus.NEEDS_REVIEW:
        return [
            (t.review, True),
            (t.contact + _by_due(due, t), True),
        ]
    short = _shortfall(status)
    if short is None:
        return [
            (t.need_proof, True),
            (t.send_proof + _by_due(due, t), True),
        ]
    month, amount = short
    return [
        (t.short.format(amount=_fmt_money(amount), month=_fmt_month(month, t)), True),
        (t.send_proof + _by_due(due, t), True),
        (t.stop, False),
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


def sms_reminder(member: Member, status: ProofKitStatus, lang: str = "en") -> str:
    """Build one SMS (<= 160 printable ASCII chars) for a member in English, Spanish or Portuguese.

    Takes the contract models ``Member`` and ``ProofKitStatus`` and returns a plain ``str``.
    ``lang`` is exactly ``"en"`` (default), ``"es"`` or ``"pt"``; anything else raises ``ValueError``.
    Reads only the display name's first token, status, dates and the first failing verification
    month's income shortfall; never ids, phone digits, exemption details, findings or action text.
    Raises ``ValueError`` before rendering if the status, wallet or exemption belongs to another member.

    The Spanish and Portuguese wording is deliberately ASCII-only (no accents, n-tilde or c-cedilla).
    A single character outside the GSM-7 alphabet (for example a-acute or c-cedilla) forces the whole
    message into UCS-2, which cuts one SMS segment from 160 to 70 characters, so the reminder would
    split into several segments or be truncated. Plain ASCII keeps every language in one 160-char SMS.
    """
    if not isinstance(lang, str) or lang not in _TEMPLATES:
        raise ValueError(f"unsupported lang {lang!r}; expected one of {sorted(_TEMPLATES)}")
    _check_member_ids(member, status)
    t = _TEMPLATES[lang]
    greeting = t.greeting.format(name=_first_name(member.display_name))
    msg = _fit(greeting, _clauses(member, status, t))
    assert all(" " <= c <= "~" for c in msg)
    return msg
