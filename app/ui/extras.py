"""Hook slots for Karthik's plug-in modules (branch final/ui-extras). Each is optional: if the module isn't
merged yet, the slot shows nothing (or a short note), so the app works before and after his merge.

Contract we ask for: `render_upload(member, wallet_rules, today)` RETURNS the list of EarningsDocument it accepted
(or None). Returned documents are added to the member's documents, so their status updates end to end.
"""
from __future__ import annotations

import importlib

import streamlit as st

from proofkit.contracts import EarningsDocument

from app.ui.common import add_earnings


def _optional(module: str, name: str):
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError):
        return None


def metric_tiles(status, today, rules=None) -> None:
    fn = _optional("app.metrics", "render_metric_tiles")
    if fn:
        fn(status, today, rules)


def sms_card(member, status) -> None:
    fn = _optional("app.sms_card", "render_sms_card")
    if fn:
        fn(member, status, key=f"sms-{member.member_id}")


def earnings_upload(member, wallet_rules, today) -> None:
    fn = _optional("app.upload", "render_upload")
    if fn is None:
        st.info("Pay-statement upload is being added (app/upload.py). Demo profiles already include theirs.")
        return
    accepted = fn(member, wallet_rules, today)
    if isinstance(accepted, list):
        docs = [d for d in accepted if isinstance(d, EarningsDocument) and d.member_id == member.member_id]
        if docs and add_earnings(member.member_id, docs):
            st.rerun()      # new statements: refresh the status everywhere


def sample_gallery(member_id: str) -> None:
    fn = _optional("app.samples", "render_sample_gallery")
    if fn:
        fn(member_id)
