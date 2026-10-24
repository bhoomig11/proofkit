"""Escaped, downloadable HTML proof packet.

Every dynamic value (names, conditions, quotes, platforms, statements, actions) goes through `_e`
(html.escape) before it reaches the HTML. Only our own static markup is unescaped.
"""
from __future__ import annotations

import html
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from proofkit.contracts import FindingsBundle, Member, ProofKitStatus

DISCLAIMER = "ProofKit organizes evidence. MassHealth makes all eligibility determinations."
SIGN_OFF = "This statement must be reviewed and signed by a licensed clinician."
STATUS_TEXT = {"protected": "Protected", "at_risk": "At risk", "needs_review": "Needs review"}
STYLE = """
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;max-width:860px;margin:2rem auto;padding:0 1rem;
color:#1b1530;line-height:1.5}h1{margin-bottom:.2rem}h2{border-bottom:2px solid #6d4aff;padding-bottom:.2rem;margin-top:2rem}
table{border-collapse:collapse;width:100%}th,td{border:1px solid #c9c2e0;padding:.4rem .6rem;text-align:left}
mark{background:#ffe58a;padding:0 .15rem}.badge{display:inline-block;padding:.2rem .7rem;border-radius:999px;font-weight:700;
border:2px solid #1b1530}.muted{color:#4a4560}pre{white-space:pre-wrap;background:#f6f4fc;padding:1rem;border-radius:8px}
footer{margin-top:2.5rem;font-weight:600}
"""


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _money(amount: Decimal) -> str:
    return f"${amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _month(month: str) -> str:
    year, mon = month.split("-")
    return date(int(year), int(mon), 1).strftime("%B %Y")


def _day(d: date) -> str:
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def build_packet_html(member: Member, status: ProofKitStatus, findings: FindingsBundle) -> str:
    """Member + ProofKitStatus + FindingsBundle -> standalone, escaped HTML proof packet."""
    parts: list[str] = [
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>",
        f"<title>ProofKit evidence packet: {_e(member.member_id)}</title><style>{STYLE}</style></head><body>",
        "<h1>ProofKit evidence packet</h1>",
        f"<p class='muted'>Member: {_e(member.display_name)} ({_e(member.member_id)}) · "
        f"Renewal: {_e(_day(member.renewal_date))}</p>",
        f"<p><span class='badge'>{_e(STATUS_TEXT.get(status.status.value, status.status.value))}</span>",
    ]
    if status.protected_by:
        parts.append(f" &nbsp;Protected by: {_e(status.protected_by.replace('_', ' '))}")
    if status.next_deadline:
        parts.append(f" &nbsp;Next deadline: {_e(_day(status.next_deadline))}")
    parts.append("</p>")

    if status.action_items:
        parts.append("<h2>What to do next</h2><ol>")
        for item in sorted(status.action_items, key=lambda a: a.priority):
            due = f" (due {_e(_day(item.due))})" if item.due else ""
            parts.append(f"<li><strong>{_e(item.title)}</strong>{due}<br>{_e(item.detail)}</li>")
        parts.append("</ol>")

    wallet = status.wallet
    if wallet and wallet.months:
        parts.append("<h2>Work hours and income by month</h2><table><tr><th>Month</th><th>Hours</th><th>Income</th>"
                     "<th>Meets rule?</th><th>Short by</th></tr>")
        for m in wallet.months:
            short = []
            if not m.qualifies:
                short = [f"{m.shortfall_hours} h", _money(m.shortfall_income)]
            parts.append(f"<tr><td>{_e(_month(m.month))}</td><td>{_e(m.total_hours)}"
                         f"{'' if m.hours_known_for_all_records else ' (some hours unknown)'}</td>"
                         f"<td>{_e(_money(m.total_income))}</td><td>{'Yes' if m.qualifies else 'No'}"
                         f"{' (' + _e(m.basis.value) + ')' if m.qualifies else ''}</td>"
                         f"<td>{_e(' or '.join(short)) if short else '-'}</td></tr>")
        parts.append("</table>")
        if wallet.records:
            parts.append("<h3>Source records</h3><ul>")
            for r in wallet.records:
                hours = f"{r.hours} h, " if r.hours is not None else ""
                parts.append(f"<li>{_e(r.platform)}: {_e(_day(r.period_start))} to {_e(_day(r.period_end))}, "
                             f"{_e(hours)}{_e(_money(r.gross_income))}<br><span class='muted'>"
                             f"Source: &ldquo;{_e(r.source_quote)}&rdquo;</span></li>")
            parts.append("</ul>")

    if findings.findings:
        parts.append("<h2>Evidence from clinical notes</h2><ul>")
        for f in sorted(findings.findings, key=lambda x: (x.note_id, x.quote_start)):
            counted = f.status.value == "current"
            parts.append(f"<li>{_e(f.icd10)} — {_e(f.condition)} — <mark>{_e(f.quote)}</mark> "
                         f"<span class='muted'>({_e(f.note_id)}, {_e(_day(f.note_date))}, "
                         f"{_e(f.status.value.replace('_', ' '))}"
                         f"{'' if counted else ', not counted'})</span></li>")
        parts.append("</ul>")

    exemption = status.exemption
    if exemption and exemption.review_reasons:
        parts.append("<h2>Needs a clinician's review</h2><ul>")
        parts += [f"<li>{_e(r)}</li>" for r in exemption.review_reasons]
        parts.append("</ul>")
    if exemption and exemption.statement_draft:
        parts.append(f"<h2>Clinician statement (draft)</h2><pre>{_e(exemption.statement_draft)}</pre>")
        if SIGN_OFF not in exemption.statement_draft:
            parts.append(f"<p><strong>{_e(SIGN_OFF)}</strong></p>")

    parts.append(f"<footer>{_e(DISCLAIMER)}</footer></body></html>")
    return "".join(parts)
