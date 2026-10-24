"""RenewRight UI extra: SMS reminder preview card (EN / ES / PT).

The message text comes from the integration SMS builder, which only ever emits printable ASCII
(<= 160 chars). It is shown with ``st.code`` so Streamlit renders it as plain, escaped text.
"""
from __future__ import annotations

from proofkit.contracts import Member, ProofKitStatus
from proofkit.integration.reminder import SMS_LIMIT, sms_reminder

__all__ = ["SMS_LANGS", "render_sms_card", "sms_preview"]

# Radio label -> language code accepted by sms_reminder.
SMS_LANGS: dict[str, str] = {"EN": "en", "ES": "es", "PT": "pt"}


def sms_preview(member: Member, status: ProofKitStatus, lang: str = "en") -> tuple[str, str]:
    """Build the SMS for a ``Member`` / ``ProofKitStatus`` pair.

    Returns ``(text, counter)`` where ``counter`` is ``"<len>/160"``. ``lang`` is "en", "es" or "pt";
    anything else raises ``ValueError`` (from ``sms_reminder``).
    """
    text = sms_reminder(member, status, lang)
    return text, f"{len(text)}/{SMS_LIMIT}"


def render_sms_card(member: Member, status: ProofKitStatus, *, key: str = "ui_extras_sms_lang") -> None:
    """Render the SMS preview for a ``Member`` / ``ProofKitStatus``: language radio, plain text, counter."""
    import streamlit as st

    choice = st.radio("Language", list(SMS_LANGS), horizontal=True, key=key)
    text, counter = sms_preview(member, status, SMS_LANGS.get(choice, "en"))
    st.code(text, language=None)
    st.caption(counter)
