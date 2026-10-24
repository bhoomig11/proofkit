"""Signed-out page: centered sign-in / create-account card and one-click demo profiles."""
from __future__ import annotations

from datetime import timedelta

import streamlit as st

from app.auth import DEMO_LOGINS, AccountStore, AuthError
from app.ui.common import APP_NAME, DEMO_STORIES, demo_data

MAX_FAILED_SIGNINS = 5


def render_auth(accounts: AccountStore) -> None:
    _, card, _ = st.columns([1, 1.1, 1])
    with card:
        st.markdown(f"<h2 class='pk-auth-title'>Welcome to {APP_NAME}</h2>"
                    "<p class='pk-auth-sub'>Keep your MassHealth coverage.</p>", unsafe_allow_html=True)
        sign_in, sign_up = st.tabs(["Sign in", "Create account"])
        with sign_in:
            _sign_in_form(accounts)
        with sign_up:
            _sign_up_form(accounts)
        st.markdown("#### Try a demo")
        with st.container(key="demo_cards"):
            for demo in DEMO_LOGINS:
                story = DEMO_STORIES.get(demo["member_id"], "")
                if st.button(f"**{demo['name']}** · {story}", key=f"demo-{demo['member_id']}",
                             use_container_width=True):
                    st.session_state.account = accounts.sign_in(demo["email"], demo["password"])
                    st.rerun()


def _sign_in_form(accounts: AccountStore) -> None:
    failed = st.session_state.get("failed_signins", 0)
    with st.form("signin", border=False):
        email = st.text_input("Email", key="signin_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="signin_password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if not submitted:
        return
    if failed >= MAX_FAILED_SIGNINS:
        st.error("Too many tries. Please wait a moment and refresh the page.")
        return
    found = accounts.sign_in(email, password)
    if found is None:
        st.session_state.failed_signins = failed + 1
        st.error("That email and password don't match.")
        return
    st.session_state.account = found
    st.session_state.failed_signins = 0
    st.rerun()


def _sign_up_form(accounts: AccountStore) -> None:
    today = demo_data().today
    with st.form("signup", border=False):
        name = st.text_input("Name", key="signup_name", autocomplete="name")
        email = st.text_input("Email", key="signup_email", autocomplete="email")
        password = st.text_input("Password", type="password", key="signup_password", autocomplete="new-password",
                                 help="At least 8 characters. Demo only: don't reuse a real password.")
        renewal = st.date_input("MassHealth renewal date", value=today + timedelta(days=90), min_value=today,
                                key="signup_renewal", format="MM/DD/YYYY")
        created = st.form_submit_button("Create account", type="primary", use_container_width=True)
    if created:
        try:
            st.session_state.account = accounts.sign_up(name, email, password, renewal)
            st.rerun()
        except AuthError as exc:
            st.error(str(exc))
