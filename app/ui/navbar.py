"""Nav bar: brand · section links · accessibility menu · user menu."""
from __future__ import annotations

import streamlit as st

from app.format import long_date
from app.highlight import escape_plain
from app.theme import pip_svg
from app.ui.common import APP_NAME, STATUS, member_for, view_for

SIGN_OUT_KEYS = ("account", "chat_messages", "chat_member", "section", "documents", "view_cache", "coach_open")


def render_navbar(account, sections: list[str] | None) -> dict:
    """Render the top bar. `sections` = links to show (None when no dashboard). Returns display settings."""
    with st.container(key="navbar"):
        brand, nav, a11y, user = st.columns([2, 7.2, 1.5, 1.5], vertical_alignment="center")
        brand.markdown(f"<div class='pk-brand'><span aria-hidden='true'>{pip_svg('protected')}</span>{APP_NAME}</div>",
                       unsafe_allow_html=True)
        if sections:
            if st.session_state.get("section") not in sections:
                st.session_state.section = sections[0]
            nav.radio("Sections", sections, horizontal=True, key="section", label_visibility="collapsed")
        with a11y.popover("Accessibility", icon=":material/accessibility_new:", use_container_width=True,
                          help="Display and accessibility options"):
            settings = {
                "theme": st.radio("Theme", ["system", "light", "dark"], horizontal=True,
                                  format_func=str.capitalize, key="theme"),
                "large": st.toggle("Larger text", value=False, key="large_text"),
                "roomy": st.toggle("More spacing", value=False, key="more_spacing"),
                "calm": st.toggle("Reduce motion", value=False, key="reduce_motion"),
                "live": st.toggle("Live AI", value=False, key="live_ai",
                                  help="Off: works offline and reads the sample documents. "
                                       "On: reads any document and powers Coverage Coach (needs an API key)."),
            }
        if account is not None:
            _user_menu(user, account, settings["live"])
    return settings


def _user_menu(col, account, live: bool) -> None:
    with col.popover(account.name.split()[0], icon=":material/account_circle:", use_container_width=True,
                     help="Your account"):
        st.markdown(f"**{escape_plain(account.name)}**")
        st.caption(account.email)
        member = member_for(account)
        view = view_for(member, live)
        st.text(f"Member ID: {member.member_id}")
        st.text(f"Status: {STATUS[view.status.status.value][0]}")
        st.text(f"Renewal: {long_date(member.renewal_date)}")
        if view.status.next_deadline:
            st.text(f"Proof due: {long_date(view.status.next_deadline)}")
        if account.email.endswith("@example.com"):
            st.caption("Demo account (synthetic person).")
        if st.button("Sign out", key="signout", icon=":material/logout:", use_container_width=True):
            for key in SIGN_OUT_KEYS:
                st.session_state.pop(key, None)
            st.rerun()
