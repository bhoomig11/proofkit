"""ProofKit Coverage Copilot: Streamlit UI.  Run:  streamlit run app/main.py

Security: every dynamic string (notes, quotes, names, answers) is either rendered with st.text / st.write of
plain values, or passed through html.escape (app.highlight.escape_plain) before any unsafe_allow_html block.
Only our own static CSS/SVG is injected unescaped.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run app/main.py` puts app/ on the path, not the repo root
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.agent_panel import render_agent_panel  # noqa: E402
from app.data import load_demo_data  # noqa: E402
from app.format import countdown, format_money, long_date, month_long, plain_protected_by  # noqa: E402
from app.highlight import escape_plain  # noqa: E402
from app.state import build_member_view, make_llm  # noqa: E402
from app.theme import build_css, pip_svg  # noqa: E402
from app.whatif import target_month, what_if_status  # noqa: E402
from proofkit.common.injection import injection_spans  # noqa: E402
from proofkit.integration import build_packet_html  # noqa: E402
from proofkit.wallet import load_wallet_rules  # noqa: E402

FRAILTY = ROOT / "config" / "frailty_rules.json"
WALLET = ROOT / "config" / "wallet_rules.json"
DISCLAIMER = "ProofKit organizes evidence. MassHealth makes all eligibility determinations."
HOURS_RULE, INCOME_RULE = Decimal("80"), Decimal("580")   # federal rule: 80 h or 80 x $7.25 per month
STATUS = {
    "protected": ("✅", "Protected", "You have what you need to keep your coverage."),
    "needs_review": ("🔎", "Needs review", "Almost there: one thing needs a person to check it."),
    "at_risk": ("⚠️", "At risk", "You could lose coverage unless you send more proof in time."),
}
STORIES = {
    "SYN-0001": "Lupus in her notes, 74 hours of gig work",
    "SYN-0002": "Notes say 'R/o CHF' and 'denies depression'; 92.5 Uber hours",
    "SYN-0003": "Severe recurrent depression; an old PTSD note",
    "SYN-0004": "No exemption; $520 in February",
    "SYN-0005": "Red team: injected 'mark exempt' and 'report 200 hours'",
}
TOUR = ["SYN-0001", "SYN-0002", "SYN-0004", "SYN-0005"]

st.set_page_config(page_title="ProofKit · Coverage Copilot", page_icon="🛡️", layout="wide")


# ───────────────────────────── data (cached) ─────────────────────────────
@st.cache_resource(show_spinner=False)
def demo_data():
    return load_demo_data(ROOT)


@st.cache_resource(show_spinner="Building the proof…")
def member_view(member_id: str):
    data = demo_data()
    offline_llm, _ = make_llm(live=False, data=data)   # evidence pipeline replays synthetic results: fast, free
    return build_member_view(member_id, data, offline_llm, FRAILTY, WALLET)


@st.cache_resource(show_spinner=False)
def coach_llm(live: bool):
    return make_llm(live=live, data=demo_data())


data = demo_data()
wallet_rules = load_wallet_rules(WALLET)
ids = list(data.members)

# ───────────────────────────── sidebar ─────────────────────────────
with st.sidebar:
    st.markdown(f"<div aria-hidden='true'>{pip_svg('protected')}</div>", unsafe_allow_html=True)
    st.title("Coverage Copilot")
    st.caption("Keep your MassHealth coverage. See what counts, what's missing, and by when.")

    if "member_id" not in st.session_state:
        st.session_state.member_id = ids[0]
    st.subheader("Who are you helping?")
    for mid in ids:
        m = data.members[mid]
        label = f"{'▶ ' if st.session_state.member_id == mid else ''}{m.display_name}"
        if st.button(label, key=f"pick-{mid}", use_container_width=True, help=STORIES.get(mid, "")):
            st.session_state.member_id = mid
            st.rerun()
        st.caption(STORIES.get(mid, ""))
    if st.button("🎬 Demo tour: next person", use_container_width=True):
        cur = st.session_state.member_id
        st.session_state.member_id = TOUR[(TOUR.index(cur) + 1) % len(TOUR)] if cur in TOUR else TOUR[0]
        st.rerun()

    st.subheader("Display")
    theme = st.radio("Theme", ["system", "light", "dark"], horizontal=True, format_func=str.capitalize)
    large = st.toggle("Larger text", value=False)
    roomy = st.toggle("More spacing", value=False)
    calm = st.toggle("Reduce motion", value=False)
    live = st.toggle("Live AI for the coach", value=False,
                     help="Off = works fully offline with verified facts only. On = needs an API key.")

st.markdown(build_css(theme, large_text=large, comfortable=roomy, reduce_motion=calm), unsafe_allow_html=True)

view = member_view(st.session_state.member_id)
status, member = view.status, view.member
llm, is_live = coach_llm(live)
icon, word, meaning = STATUS[status.status.value]


def card(html_body: str) -> None:
    """Render trusted markup; callers escape every dynamic value first."""
    st.markdown(f"<div class='pk-card'>{html_body}</div>", unsafe_allow_html=True)


# ───────────────────────────── header ─────────────────────────────
main, side = st.columns([2, 1], gap="large")
with main:
    hero_l, hero_r = st.columns([1, 4])
    with hero_l:
        st.markdown(pip_svg(status.status.value), unsafe_allow_html=True)
    with hero_r:
        due = status.next_deadline
        chips = [f"<span class='pk-chip'>{escape_plain(countdown(data.today, due))}</span>"] if due else []
        how = plain_protected_by(status.protected_by)
        if how:
            chips.append(f"<span class='pk-chip'>Protected by: {escape_plain(how)}</span>")
        st.markdown(
            f"<div role='status' aria-live='polite'><h2 class='pk-status-{status.status.value}' style='margin:0'>"
            f"{icon} {escape_plain(member.display_name)} is {word.lower()}</h2>"
            f"<p style='margin:.2rem 0 .6rem'>{escape_plain(meaning)}</p>{' '.join(chips)}</div>",
            unsafe_allow_html=True)
    if status.status.value == "protected" and not calm and st.session_state.get("cheered") != member.member_id:
        st.session_state.cheered = member.member_id
        st.balloons()

    tabs = st.tabs(["✅ Next steps", "💡 Why", "📄 Evidence", "⏱️ Hours & money", "📦 Proof packet", "🛡️ Red team"])

    # ── next steps
    with tabs[0]:
        if not status.action_items:
            st.success("Nothing to do right now. Keep your proof packet handy for renewal.")
        for i, item in enumerate(sorted(status.action_items, key=lambda a: a.priority)):
            done = st.checkbox(item.title, key=f"act-{member.member_id}-{i}")
            st.caption(("✔ Done. " if done else "") + item.detail + (f" Due {long_date(item.due)}." if item.due else ""))
        st.caption(f"Renewal date: {long_date(member.renewal_date)}")

    # ── why
    with tabs[1]:
        ex = status.exemption
        if ex is not None:
            st.markdown("#### Medical exemption check")
            st.write({"exempt": "✅ Exempt (medically frail)", "not_exempt": "Not exempt from the notes",
                      "needs_clinician_review": "🔎 A clinician needs to confirm"}[ex.outcome.value])
            for mr in ex.matched_rules:
                st.text(f"• {mr.rule_id}: {mr.rationale}")
            for reason in ex.review_reasons:
                st.text(f"• {reason}")
            st.caption(f"Looks back {ex.lookback_months} months from {long_date(ex.as_of)} · rules {ex.rules_version}")
        if status.wallet is not None:
            st.markdown("#### Work requirement check (80 hours or $580 a month)")
            for m in status.wallet.months:
                verdict = f"meets the rule by {m.basis.value}" if m.qualifies else "does not meet the rule yet"
                st.text(f"• {month_long(m.month)}: {m.total_hours} hours, {format_money(m.total_income)}: {verdict}")
        st.caption(DISCLAIMER)

    # ── evidence
    with tabs[2]:
        st.caption("Highlighted = counts as evidence. Struck through = found but not counted (denied, ruled out, family, past).")
        for note in data.notes.get(member.member_id, []):
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

    # ── hours & money + what-if
    with tabs[3]:
        w = status.wallet
        if w is None or not w.months:
            st.info("No earnings statements yet.")
        else:
            for m in w.months:
                st.markdown(f"**{month_long(m.month)}** {'· 🏅 proof badge' if m.qualifies else ''}")
                c1, c2 = st.columns(2)
                c1.progress(min(float(m.total_hours / HOURS_RULE), 1.0), text=f"{m.total_hours} of 80 hours")
                c2.progress(min(float(m.total_income / INCOME_RULE), 1.0),
                            text=f"{format_money(m.total_income)} of $580.00")
                if not m.qualifies:
                    st.caption(f"Short by {m.shortfall_hours} hours or {format_money(m.shortfall_income)}.")
            st.markdown("#### 🔮 What if…")
            month = target_month(w)
            st.caption(f"Try adding work in {month_long(month)}. This is a preview only: your real result does not change.")
            extra_h = st.slider("Extra hours (work, school or volunteering)", 0, 80, 0, key=f"wh-{member.member_id}")
            extra_i = st.slider("Extra income ($)", 0, 600, 0, step=10, key=f"wi-{member.member_id}")
            after = what_if_status(view, wallet_rules, data.today, extra_hours=Decimal(extra_h),
                                   extra_income=Decimal(extra_i), month=month)
            a_icon, a_word, _ = STATUS[after.status.value]
            st.markdown(f"**Now:** {icon} {word} → **With this change:** {a_icon} {a_word}")
            if after.status.value == "protected" and status.status.value != "protected":
                st.success("That would be enough. Ask your employer or platform for a statement showing it.")
                if not calm and st.session_state.get("whatif_cheer") != (member.member_id, extra_h, extra_i):
                    st.session_state.whatif_cheer = (member.member_id, extra_h, extra_i)
                    st.balloons()

    # ── packet
    with tabs[4]:
        packet = build_packet_html(member, status, view.findings)
        st.write("One file with your status, monthly proof, evidence quotes and next steps. Bring it to your "
                 "navigator or clinic.")
        st.download_button("⬇️ Download proof packet (HTML)", packet.encode("utf-8"),
                           file_name=f"proofkit-{member.member_id}.html", mime="text/html")

    # ── red team
    with tabs[5]:
        injected = []
        for note in data.notes.get(member.member_id, []):
            injected += [("clinical note " + note.note_id, note.text[s:e]) for s, e in injection_spans(note.text)]
        for doc in data.documents.get(member.member_id, []):
            if doc.content_text:
                injected += [("pay statement " + doc.doc_id, doc.content_text[s:e])
                             for s, e in injection_spans(doc.content_text)]
        if not injected:
            st.info("No hidden instructions found in this person's documents. Try the red-team persona (SYN-0005).")
        else:
            st.warning("These documents contain hidden instructions trying to trick the AI. ProofKit treats them as data:")
            for where, text in injected:
                st.text(f"Ignored in {where}: {text.strip()}")
            st.success(f"Result is unchanged: {word}. Findings: "
                       + (", ".join(f.condition for f in view.findings.findings) or "none")
                       + ". The decision comes from fixed, tested rules, not from the AI.")
            if status.wallet is not None:
                for m in status.wallet.months:
                    st.text(f"{month_long(m.month)}: {m.total_hours} hours, {format_money(m.total_income)} (not 200 hours / $5,000)")

# ───────────────────────────── agent panel ─────────────────────────────
with side:
    st.markdown(f"<span class='pk-chip'>{'🟢 Live AI on' if is_live else '⚪ Live AI off: verified facts only'}</span>",
                unsafe_allow_html=True)
    if live and not is_live:
        st.caption("No API key found, so the coach is running offline.")
    render_agent_panel(view=view, llm=llm, wallet_rules=wallet_rules, today=data.today)

st.divider()
st.caption(f"{DISCLAIMER} All people shown are synthetic. Demo date: {long_date(data.today)}.")
