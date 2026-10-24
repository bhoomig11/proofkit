"""RenewRight: Streamlit entry point. Routes between the sign-in page and the member dashboard.

Run:  streamlit run app/main.py

Screens live in app/ui/ (navbar, auth_page, dashboard, documents, extras). Coverage Coach is its own widget
(app/coach_widget.py). Security: dynamic text is rendered with st.text or escaped (app.highlight.escape_plain)
before any unsafe_allow_html; only our static CSS/SVG is injected unescaped. Passwords: app/auth.py (hashed).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # `streamlit run app/main.py` puts app/ on the path, not the repo root
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from app.auth import AccountStore  # noqa: E402
from app.coach_widget import render_coach_widget  # noqa: E402
from app.format import long_date  # noqa: E402
from app.theme import build_css  # noqa: E402
from app.ui.auth_page import render_auth  # noqa: E402
from app.ui.common import APP_NAME, DISCLAIMER, WALLET, demo_data, llm_for, member_for, view_for  # noqa: E402
from app.ui.dashboard import render_dashboard, sections_for  # noqa: E402
from app.ui.navbar import render_navbar  # noqa: E402
from app.ui.style import PAGE_CSS  # noqa: E402
from proofkit.wallet import load_wallet_rules  # noqa: E402

st.set_page_config(page_title=APP_NAME, layout="wide")

data = demo_data()
wallet_rules = load_wallet_rules(WALLET)
account = st.session_state.get("account")
member = member_for(account) if account is not None else None

st.markdown(PAGE_CSS, unsafe_allow_html=True)
settings = render_navbar(account, sections_for(member.member_id) if member else None)
st.markdown(build_css(settings["theme"], large_text=settings["large"], comfortable=settings["roomy"],
                      reduce_motion=settings["calm"]), unsafe_allow_html=True)

if member is None:
    render_auth(AccountStore())
else:
    view = view_for(member, settings["live"])
    render_dashboard(view, section=st.session_state.get("section", "Next steps"), wallet_rules=wallet_rules,
                     today=data.today, calm=settings["calm"], live=settings["live"])
    llm, is_live = llm_for(settings["live"])
    render_coach_widget(view=view, llm=llm, wallet_rules=wallet_rules, today=data.today, is_live=is_live,
                        live_requested=settings["live"])

st.divider()
st.caption(f"{DISCLAIMER} All people shown are synthetic. Demo date: {long_date(data.today)}.")
