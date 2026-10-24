"""RenewRight: Streamlit UI with sign-in, header, member dashboard and the Coverage Coach.

Run:  streamlit run app/main.py

Security: every dynamic string (notes, quotes, names, answers) is rendered with st.text / plain values, or passed
through html.escape (app.highlight.escape_plain) before any unsafe_allow_html block. Only our own static CSS/SVG
is injected unescaped. Passwords are salted PBKDF2 hashes (app/auth.py).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run app/main.py` puts app/ on the path, not the repo root
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.coach_widget import render_coach_widget  # noqa: E402
from app.auth import DEMO_LOGINS, AccountStore, AuthError  # noqa: E402
from app.data import load_demo_data  # noqa: E402
from app.format import countdown, format_money, long_date, month_long, plain_protected_by  # noqa: E402
from app.highlight import escape_plain  # noqa: E402
from app.state import build_member_view, make_llm  # noqa: E402
from app.theme import build_css, pip_svg  # noqa: E402
from app.whatif import target_month, what_if_status  # noqa: E402
from proofkit.common.injection import injection_spans  # noqa: E402
from proofkit.integration import build_packet_html  # noqa: E402
from proofkit.wallet import load_wallet_rules  # noqa: E402

APP_NAME = "RenewRight"
FRAILTY = ROOT / "config" / "frailty_rules.json"
WALLET = ROOT / "config" / "wallet_rules.json"
DISCLAIMER = "RenewRight organizes evidence. MassHealth makes all eligibility determinations."
HOURS_RULE, INCOME_RULE = Decimal("80"), Decimal("580")   # federal rule: 80 h or 80 x $7.25 per month
MAX_FAILED_SIGNINS = 5
STATUS = {
    "protected": ("Protected", "You have what you need to keep your coverage."),
    "needs_review": ("Needs review", "Almost there: one thing needs a person to check it."),
    "at_risk": ("At risk", "You could lose coverage unless you send more proof in time."),
}
STORIES = {
    "SYN-0001": "Lupus in her notes, 74 hours of gig work",
    "SYN-0002": "Notes say 'R/o CHF' and 'denies depression'; 92.5 hours",
    "SYN-0003": "Severe recurrent depression; an old PTSD note",
    "SYN-0004": "No exemption; $520 in February",
    "SYN-0005": "Red team: injected 'mark exempt' and 'report 200 hours'",
}
EXAMPLE_MEMBER = "SYN-0001"

st.set_page_config(page_title=APP_NAME, layout="wide")


# ───────────────────────────── data (cached) ─────────────────────────────
@st.cache_resource(show_spinner=False)
def demo_data():
    return load_demo_data(ROOT)


@st.cache_resource(show_spinner="Building your proof…")
def member_view(member_id: str):
    data = demo_data()
    offline_llm, _ = make_llm(live=False, data=data)   # evidence pipeline replays synthetic results: fast, free
    return build_member_view(member_id, data, offline_llm, FRAILTY, WALLET)


@st.cache_resource(show_spinner=False)
def coach_llm(live: bool):
    return make_llm(live=live, data=demo_data())


data = demo_data()
wallet_rules = load_wallet_rules(WALLET)
accounts = AccountStore()
account = st.session_state.get("account")

# ───────────────────────────── nav bar ─────────────────────────────
SECTIONS = ["Next steps", "Why", "Evidence", "Hours & money", "Proof packet", "Red team"]
NAV_CSS = """<style>
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stHeader"]{display:none}
.block-container{padding-top:1rem!important}
.pk-brand{display:flex;align-items:center;gap:.5rem;font-size:1.35rem;font-weight:800;line-height:1;white-space:nowrap}
.pk-brand svg{width:34px;height:38px}
.pk-auth h2{text-align:center;margin-bottom:.25rem}
/* radios as pill links: section nav + theme picker */
div[role="radiogroup"]{gap:.3rem;flex-wrap:wrap}
div[role="radiogroup"] label{padding:.3rem .85rem;border-radius:999px;border:1px solid var(--pk-border);cursor:pointer;margin:0}
div[role="radiogroup"] label > div:first-child{display:none}
div[role="radiogroup"] label:has(input:checked){background:var(--pk-accent);border-color:var(--pk-accent)}
div[role="radiogroup"] label:has(input:checked) p{color:var(--pk-accent-text);font-weight:700}
div[role="radiogroup"] label:has(input:focus-visible){outline:3px solid var(--pk-focus);outline-offset:2px}
.pk-status-dot{width:64px;height:64px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:1.9rem;font-weight:900;color:#fff;border:3px solid var(--pk-surface);box-shadow:0 0 0 3px var(--pk-border)}
.pk-dot-ok{background:#1A7F55}.pk-dot-risk{background:#B3263D}
</style>"""


def viewing_member_id() -> str | None:
    """The member whose dashboard is shown: an example the user opened, else their own linked record."""
    if account is None:
        return None
    return st.session_state.get("example") or account.member_id


def render_navbar() -> dict:
    """Brand · section links · accessibility menu · user menu. Returns the display settings."""
    member_id = viewing_member_id()
    brand, nav, a11y, user = st.columns([2.1, 7, 1.5, 1.6], vertical_alignment="center")
    brand.markdown(f"<div class='pk-brand'><span aria-hidden='true'>{pip_svg('protected')}</span>{APP_NAME}</div>",
                   unsafe_allow_html=True)
    if member_id:
        nav.radio("Sections", SECTIONS, horizontal=True, key="section", label_visibility="collapsed")
    with a11y.popover("Accessibility", icon=":material/accessibility_new:", use_container_width=True,
                      help="Display and accessibility options"):
        settings = {
            "theme": st.radio("Theme", ["system", "light", "dark"], horizontal=True, format_func=str.capitalize,
                              key="theme"),
            "large": st.toggle("Larger text", value=False, key="large_text"),
            "roomy": st.toggle("More spacing", value=False, key="more_spacing"),
            "calm": st.toggle("Reduce motion", value=False, key="reduce_motion"),
            "live": st.toggle("Live AI for Coverage Coach", value=False, key="live_ai",
                              help="Off = works fully offline with verified facts only. On = needs an API key."),
        }
    if account is not None:
        with user.popover(account.name.split()[0], icon=":material/account_circle:", use_container_width=True,
                          help="Your account"):
            st.markdown(f"**{escape_plain(account.name)}**")
            st.caption(account.email)
            if account.member_id:
                linked = member_view(account.member_id)
                st.text(f"Member ID: {account.member_id}")
                st.text(f"Status: {STATUS[linked.status.status.value][0]}")
                st.text(f"Renewal: {long_date(linked.member.renewal_date)}")
                if linked.status.next_deadline:
                    st.text(f"Proof due: {long_date(linked.status.next_deadline)}")
            else:
                st.text("No records linked yet.")
            if account.email.endswith("@example.com") and account.member_id:
                st.caption("Demo account (synthetic person).")
            st.divider()
            if st.button("Sign out", key="signout", icon=":material/logout:", use_container_width=True):
                for key in ("account", "chat_messages", "chat_member", "example", "section"):
                    st.session_state.pop(key, None)
                st.rerun()
    st.divider()
    return settings


st.markdown(NAV_CSS, unsafe_allow_html=True)
_settings = render_navbar()
theme, large, roomy = _settings["theme"], _settings["large"], _settings["roomy"]
calm, live = _settings["calm"], _settings["live"]
st.markdown(build_css(theme, large_text=large, comfortable=roomy, reduce_motion=calm), unsafe_allow_html=True)


# ───────────────────────────── sign in / create account ─────────────────────────────
def render_auth() -> None:
    _, middle, _ = st.columns([1, 1.15, 1])
    with middle:
        st.markdown("<div class='pk-auth'><h2>Welcome to RenewRight</h2></div>", unsafe_allow_html=True)
        sign_in, sign_up = st.tabs(["Sign in", "Create account"])
        with sign_in:
            failed = st.session_state.get("failed_signins", 0)
            with st.form("signin", border=False):
                email = st.text_input("Email", key="signin_email", autocomplete="email")
                password = st.text_input("Password", type="password", key="signin_password",
                                         autocomplete="current-password")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
            if submitted:
                if failed >= MAX_FAILED_SIGNINS:
                    st.error("Too many tries. Please wait a moment and refresh the page.")
                else:
                    found = accounts.sign_in(email, password)
                    if found is None:
                        st.session_state.failed_signins = failed + 1
                        st.error("That email and password don't match.")
                    else:
                        st.session_state.account = found
                        st.session_state.failed_signins = 0
                        st.rerun()
            with st.expander("Demo accounts"):
                for d in DEMO_LOGINS:
                    st.text(f"{d['email']}  ·  {d['password']}")
        with sign_up:
            with st.form("signup", border=False):
                name = st.text_input("Name", key="signup_name", autocomplete="name")
                new_email = st.text_input("Email", key="signup_email", autocomplete="email")
                new_password = st.text_input("Password", type="password", key="signup_password",
                                             autocomplete="new-password", help="At least 8 characters.")
                created = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if created:
                try:
                    st.session_state.account = accounts.sign_up(name, new_email, new_password)
                    st.rerun()
                except AuthError as exc:
                    st.error(str(exc))


# ───────────────────────────── new account: onboarding ─────────────────────────────
def render_onboarding() -> None:
    st.markdown(f"## Welcome, {escape_plain(account.name)}!", unsafe_allow_html=True)
    st.write("Your account is ready. Here's how RenewRight will help you keep your coverage:")
    st.markdown("1. **Add your proof**: clinical notes from your clinic, and pay statements from your gig apps.\n"
                "2. **We check it** against the 2027 rules: an exemption, or 80 hours / $580 a month.\n"
                "3. **You get a plan**: what counts, what's missing, the deadline, and a proof packet to send.")
    st.info("Uploading your own documents is coming next. Meanwhile, explore an example member to see how it works.")
    if st.button("Explore an example member (Maria)", type="primary"):
        st.session_state.example = EXAMPLE_MEMBER
        st.rerun()


# ───────────────────────────── member dashboard ─────────────────────────────
def render_dashboard(member_id: str, *, example: bool) -> None:
    view = member_view(member_id)
    status, member = view.status, view.member
    llm, is_live = coach_llm(live)
    word, meaning = STATUS[status.status.value]
    if example:
        c1, c2 = st.columns([5, 1.4], vertical_alignment="center")
        c1.info(f"You're viewing an example member ({escape_plain(member.display_name)}), not your own records.")
        if c2.button("Back to my account", use_container_width=True):
            st.session_state.pop("example", None)
            st.rerun()

    main = st.container()
    with main:
        hero_l, hero_r = st.columns([1, 9], vertical_alignment="center")
        with hero_l:
            ok = status.status.value == "protected"
            st.markdown(f"<div class='pk-status-dot {'pk-dot-ok' if ok else 'pk-dot-risk'}' role='img' "
                        f"aria-label='Status: {escape_plain(word)}'>{'✓' if ok else '!'}</div>",
                        unsafe_allow_html=True)
        with hero_r:
            due = status.next_deadline
            chips = [f"<span class='pk-chip'>{escape_plain(countdown(data.today, due))}</span>"] if due else []
            how = plain_protected_by(status.protected_by)
            if how:
                chips.append(f"<span class='pk-chip'>Protected by: {escape_plain(how)}</span>")
            st.markdown(
                f"<div role='status' aria-live='polite'><h2 class='pk-status-{status.status.value}' style='margin:0'>"
                f"{escape_plain(member.display_name)} is {word.lower()}</h2>"
                f"<p style='margin:.2rem 0 .6rem'>{escape_plain(meaning)}</p>{' '.join(chips)}</div>",
                unsafe_allow_html=True)
        if status.status.value == "protected" and not calm and st.session_state.get("cheered") != member.member_id:
            st.session_state.cheered = member.member_id
            st.balloons()

        section = st.session_state.get("section", SECTIONS[0])

        # ── next steps
        if section == SECTIONS[0]:
            if not status.action_items:
                st.success("Nothing to do right now. Keep your proof packet handy for renewal.")
            for i, item in enumerate(sorted(status.action_items, key=lambda a: a.priority)):
                done = st.checkbox(item.title, key=f"act-{member.member_id}-{i}")
                st.caption(("Done. " if done else "") + item.detail + (f" Due {long_date(item.due)}." if item.due else ""))
            st.caption(f"Renewal date: {long_date(member.renewal_date)}")

        # ── why
        if section == SECTIONS[1]:
            ex = status.exemption
            if ex is not None:
                st.markdown("#### Medical exemption check")
                st.write({"exempt": "Exempt (medically frail)", "not_exempt": "Not exempt from the notes",
                          "needs_clinician_review": "A clinician needs to confirm"}[ex.outcome.value])
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
        if section == SECTIONS[2]:
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
        if section == SECTIONS[3]:
            w = status.wallet
            if w is None or not w.months:
                st.info("No earnings statements yet.")
            else:
                for m in w.months:
                    st.markdown(f"**{month_long(m.month)}** {'· proof complete' if m.qualifies else ''}")
                    c1, c2 = st.columns(2)
                    c1.progress(min(float(m.total_hours / HOURS_RULE), 1.0), text=f"{m.total_hours} of 80 hours")
                    c2.progress(min(float(m.total_income / INCOME_RULE), 1.0),
                                text=f"{format_money(m.total_income)} of $580.00")
                    if not m.qualifies:
                        st.caption(f"Short by {m.shortfall_hours} hours or {format_money(m.shortfall_income)}.")
                st.markdown("#### What if…")
                month = target_month(w)
                st.caption(f"Try adding work in {month_long(month)}. This is a preview only: your real result does not change.")
                extra_h = st.slider("Extra hours (work, school or volunteering)", 0, 80, 0, key=f"wh-{member.member_id}")
                extra_i = st.slider("Extra income ($)", 0, 600, 0, step=10, key=f"wi-{member.member_id}")
                after = what_if_status(view, wallet_rules, data.today, extra_hours=Decimal(extra_h),
                                       extra_income=Decimal(extra_i), month=month)
                a_word, _ = STATUS[after.status.value]
                st.markdown(f"**Now:** {word} → **With this change:** {a_word}")
                if after.status.value == "protected" and status.status.value != "protected":
                    st.success("That would be enough. Ask your employer or platform for a statement showing it.")
                    if not calm and st.session_state.get("whatif_cheer") != (member.member_id, extra_h, extra_i):
                        st.session_state.whatif_cheer = (member.member_id, extra_h, extra_i)
                        st.balloons()

        # ── packet
        if section == SECTIONS[4]:
            packet = build_packet_html(member, status, view.findings)
            st.write("One file with your status, monthly proof, evidence quotes and next steps. Bring it to your "
                     "navigator or clinic.")
            st.download_button("Download proof packet (HTML)", packet.encode("utf-8"),
                               file_name=f"renewright-{member.member_id}.html", mime="text/html")

        # ── red team
        if section == SECTIONS[5]:
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
                st.warning("These documents contain hidden instructions trying to trick the AI. RenewRight treats them as data:")
                for where, text in injected:
                    st.text(f"Ignored in {where}: {text.strip()}")
                st.success(f"Result is unchanged: {word}. Findings: "
                           + (", ".join(f.condition for f in view.findings.findings) or "none")
                           + ". The decision comes from fixed, tested rules, not from the AI.")
                if status.wallet is not None:
                    for m in status.wallet.months:
                        st.text(f"{month_long(m.month)}: {m.total_hours} hours, {format_money(m.total_income)} (not 200 hours / $5,000)")

    # ───────────────────────────── agent panel ─────────────────────────────
    # Coverage Coach lives in its own module (app/coach_widget.py): floating launcher + right-side panel.
    render_coach_widget(view=view, llm=llm, wallet_rules=wallet_rules, today=data.today, is_live=is_live,
                        live_requested=live)

# ───────────────────────────── page ─────────────────────────────
if account is None:
    render_auth()
elif st.session_state.get("example"):
    render_dashboard(st.session_state.example, example=True)
elif account.member_id:
    render_dashboard(account.member_id, example=False)
else:
    render_onboarding()

st.divider()
st.caption(f"{DISCLAIMER} All people shown are synthetic. Demo date: {long_date(data.today)}.")
