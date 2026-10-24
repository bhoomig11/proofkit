"""Member dashboard: status header + the section chosen in the nav bar."""
from __future__ import annotations

from decimal import Decimal

import streamlit as st

from app.format import countdown, format_money, long_date, month_long, plain_protected_by
from app.highlight import escape_plain
from app.ui import extras
from app.ui.common import (DISCLAIMER, EMPTY_MESSAGE, HOURS_RULE, INCOME_RULE, RED_TEAM_MEMBERS, STATUS,
                           documents)
from app.ui.documents import render_documents
from app.whatif import target_month, what_if_status
from proofkit.common.injection import injection_spans
from proofkit.integration import build_packet_html

BASE_SECTIONS = ["Next steps", "Documents", "Why", "Evidence", "Hours & money", "Proof packet"]


def sections_for(member_id: str) -> list[str]:
    return BASE_SECTIONS + (["Red team"] if member_id in RED_TEAM_MEMBERS else [])


def render_dashboard(view, *, section: str, wallet_rules, today, calm: bool, live: bool) -> None:
    status, member = view.status, view.member
    docs = documents(member.member_id)
    has_docs = bool(docs["notes"] or docs["earnings"])
    _hero(view, today, has_docs)
    extras.metric_tiles(status, today)
    if status.status.value == "protected" and not calm and st.session_state.get("cheered") != member.member_id:
        st.session_state.cheered = member.member_id
        st.balloons()

    render = {
        "Next steps": lambda: _next_steps(view, has_docs),
        "Documents": lambda: render_documents(member, wallet_rules, today, live),
        "Why": lambda: _why(view),
        "Evidence": lambda: _evidence(view, docs["notes"]),
        "Hours & money": lambda: _money(view, wallet_rules, today, calm),
        "Proof packet": lambda: _packet(view),
        "Red team": lambda: _red_team(view, docs),
    }
    render.get(section, render["Next steps"])()


def _hero(view, today, has_docs: bool) -> None:
    status, member = view.status, view.member
    word, meaning = STATUS[status.status.value]
    if not has_docs:
        meaning = EMPTY_MESSAGE
    dot, text = st.columns([1, 11], vertical_alignment="center")
    ok = status.status.value == "protected"
    dot.markdown(f"<div class='pk-status-dot {'pk-dot-ok' if ok else 'pk-dot-risk'}' role='img' "
                 f"aria-label='Status: {escape_plain(word)}'>{'✓' if ok else '!'}</div>", unsafe_allow_html=True)
    chips = []
    if status.next_deadline:
        chips.append(f"<span class='pk-chip'>{escape_plain(countdown(today, status.next_deadline))}</span>")
    how = plain_protected_by(status.protected_by)
    if how:
        chips.append(f"<span class='pk-chip'>Protected by: {escape_plain(how)}</span>")
    text.markdown(
        f"<div role='status' aria-live='polite'><h2 class='pk-status-{status.status.value}' style='margin:0'>"
        f"{escape_plain(member.display_name)} is {word.lower()}</h2>"
        f"<p style='margin:.2rem 0 .5rem'>{escape_plain(meaning)}</p>{' '.join(chips)}</div>",
        unsafe_allow_html=True)


def _next_steps(view, has_docs: bool) -> None:
    status, member = view.status, view.member
    if not has_docs:
        st.info("Start in **Documents**: add a clinical note or a pay statement (or a sample).")
    if not status.action_items:
        st.success("Nothing to do right now. Keep your proof packet handy for renewal.")
    for i, item in enumerate(sorted(status.action_items, key=lambda a: a.priority)):
        done = st.checkbox(item.title, key=f"act-{member.member_id}-{i}")
        st.caption(("Done. " if done else "") + item.detail + (f" Due {long_date(item.due)}." if item.due else ""))
    st.caption(f"Renewal date: {long_date(member.renewal_date)}")
    extras.sms_card(member, status)


def _why(view) -> None:
    ex, wallet = view.exemption, view.status.wallet
    st.markdown("#### Medical exemption check")
    if ex is None:
        st.write("No clinical notes yet, so there's nothing to check for an exemption.")
    else:
        st.write({"exempt": "Exempt (medically frail)", "not_exempt": "Not exempt from the notes",
                  "needs_clinician_review": "A clinician needs to confirm"}[ex.outcome.value])
        for mr in ex.matched_rules:
            st.text(f"• {mr.rule_id}: {mr.rationale}")
        for reason in ex.review_reasons:
            st.text(f"• {reason}")
        st.caption(f"Looks back {ex.lookback_months} months from {long_date(ex.as_of)} · rules {ex.rules_version}")
    st.markdown("#### Work requirement check (80 hours or $580 a month)")
    if wallet is None or not wallet.months:
        st.write("No pay statements yet.")
    else:
        for m in wallet.months:
            verdict = f"meets the rule by {m.basis.value}" if m.qualifies else "does not meet the rule yet"
            st.text(f"• {month_long(m.month)}: {m.total_hours} hours, {format_money(m.total_income)}: {verdict}")
    st.caption(DISCLAIMER)


def _evidence(view, notes) -> None:
    ex = view.exemption
    if not notes:
        st.info("No clinical notes yet. Add one in **Documents**.")
        return
    st.caption("Highlighted = counts as evidence. Struck through = found but not counted "
               "(denied, ruled out, family, past).")
    for note in notes:
        spans = sorted((f for f in view.findings.findings if f.note_id == note.note_id), key=lambda f: f.quote_start)
        out, pos = [], 0
        for f in spans:
            if f.quote_start < pos or note.text[f.quote_start:f.quote_end] != f.quote:
                continue   # skip overlaps / anything not exactly grounded
            out.append(escape_plain(note.text[pos:f.quote_start]))
            quote = escape_plain(note.text[f.quote_start:f.quote_end])
            if f.status.value == "current":
                out.append(f"<mark title='{escape_plain(f.icd10)}'>{quote}</mark>")
            else:
                out.append(f"<span class='pk-not-counted' title='{escape_plain(f.status.value)}'>{quote}</span>")
            pos = f.quote_end
        out.append(escape_plain(note.text[pos:]))
        with st.expander(f"Note {note.note_id} · {long_date(note.note_date)}", expanded=True):
            st.markdown(f"<div class='pk-note'>{''.join(out)}</div>", unsafe_allow_html=True)
            for f in spans:
                tag = "counts" if f.status.value == "current" else f"not counted: {f.status.value.replace('_', ' ')}"
                st.text(f"{f.icd10} · {f.condition} · {tag} · confidence {f.confidence:.2f}")
    if ex is not None and ex.statement_draft:
        with st.expander("Clinician statement (draft to review and sign)"):
            st.text(ex.statement_draft)


def _money(view, wallet_rules, today, calm: bool) -> None:
    status, member, w = view.status, view.member, view.status.wallet
    word = STATUS[status.status.value][0]
    if w is None or not w.months:
        st.info("No pay statements yet. Add them in **Documents**.")
        return
    for m in w.months:
        st.markdown(f"**{month_long(m.month)}** {'· proof complete' if m.qualifies else ''}")
        c1, c2 = st.columns(2)
        c1.progress(min(float(m.total_hours / HOURS_RULE), 1.0), text=f"{m.total_hours} of 80 hours")
        c2.progress(min(float(m.total_income / INCOME_RULE), 1.0), text=f"{format_money(m.total_income)} of $580.00")
        if not m.qualifies:
            st.caption(f"Short by {m.shortfall_hours} hours or {format_money(m.shortfall_income)}.")
    st.markdown("#### What if…")
    month = target_month(w)
    st.caption(f"Try adding work in {month_long(month)}. This is a preview only: your real result does not change.")
    extra_h = st.slider("Extra hours (work, school or volunteering)", 0, 80, 0, key=f"wh-{member.member_id}")
    extra_i = st.slider("Extra income ($)", 0, 600, 0, step=10, key=f"wi-{member.member_id}")
    after = what_if_status(view, wallet_rules, today, extra_hours=Decimal(extra_h), extra_income=Decimal(extra_i),
                           month=month)
    st.markdown(f"**Now:** {word} → **With this change:** {STATUS[after.status.value][0]}")
    if after.status.value == "protected" and status.status.value != "protected":
        st.success("That would be enough. Ask your employer or platform for a statement showing it.")
        if not calm and st.session_state.get("whatif_cheer") != (member.member_id, extra_h, extra_i):
            st.session_state.whatif_cheer = (member.member_id, extra_h, extra_i)
            st.balloons()


def _packet(view) -> None:
    packet = build_packet_html(view.member, view.status, view.findings)
    st.write("One file with your status, monthly proof, evidence quotes and next steps. "
             "Bring it to your navigator or clinic.")
    st.download_button("Download proof packet (HTML)", packet.encode("utf-8"),
                       file_name=f"renewright-{view.member.member_id}.html", mime="text/html", type="primary")


def _red_team(view, docs) -> None:
    status = view.status
    word = STATUS[status.status.value][0]
    injected = []
    for note in docs["notes"]:
        injected += [("clinical note " + note.note_id, note.text[s:e]) for s, e in injection_spans(note.text)]
    for doc in docs["earnings"]:
        if doc.content_text:
            injected += [("pay statement " + doc.doc_id, doc.content_text[s:e])
                         for s, e in injection_spans(doc.content_text)]
    if not injected:
        st.info("No hidden instructions found in these documents.")
        return
    st.warning("These documents contain hidden instructions trying to trick the AI. RenewRight treats them as data:")
    for where, text in injected:
        st.text(f"Ignored in {where}: {text.strip()}")
    st.success(f"Result is unchanged: {word}. Findings: "
               + (", ".join(f.condition for f in view.findings.findings) or "none")
               + ". The decision comes from fixed, tested rules, not from the AI.")
    if status.wallet is not None:
        for m in status.wallet.months:
            st.text(f"{month_long(m.month)}: {m.total_hours} hours, {format_money(m.total_income)} "
                    "(not 200 hours / $5,000)")
