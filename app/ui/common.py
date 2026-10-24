"""Shared UI constants, cached data, the per-user document store, and the view builder."""
from __future__ import annotations

import hashlib
from decimal import Decimal
from pathlib import Path

import streamlit as st

from app.data import load_demo_data
from app.state import MemberView, build_view, make_llm
from proofkit.contracts import ClinicalNote, EarningsDocument, Member

ROOT = Path(__file__).resolve().parents[2]
FRAILTY = ROOT / "config" / "frailty_rules.json"
WALLET = ROOT / "config" / "wallet_rules.json"
APP_NAME = "RenewRight"
DISCLAIMER = "RenewRight organizes evidence. MassHealth makes all eligibility determinations."
HOURS_RULE, INCOME_RULE = Decimal("80"), Decimal("580")   # federal rule: 80 h or 80 x $7.25 per month
STATUS = {
    "protected": ("Protected", "You have what you need to keep your coverage."),
    "needs_review": ("Needs review", "Almost there: one thing needs a person to check it."),
    "at_risk": ("At risk", "You could lose coverage unless you send more proof in time."),
}
EMPTY_MESSAGE = "Add your documents so RenewRight can check your coverage."
DEMO_STORIES = {
    "SYN-0001": "Lupus in her notes · 74 gig hours",
    "SYN-0002": "'R/o CHF', 'denies depression' · 92.5 hours",
    "SYN-0003": "Severe recurrent depression · old PTSD note",
    "SYN-0004": "No exemption · $520 in February",
    "SYN-0005": "Hidden 'mark me exempt' instructions",
}
RED_TEAM_MEMBERS = {"SYN-0005"}


@st.cache_resource(show_spinner=False)
def demo_data():
    return load_demo_data(ROOT)


def llm_for(live: bool):
    """(llm, is_live). Offline replay reads the sample documents; Live AI (API key) reads anything."""
    return _llm(live)


@st.cache_resource(show_spinner=False)
def _llm(live: bool):
    return make_llm(live=live, data=demo_data())


def member_for(account) -> Member:
    """The signed-in user's member record: a demo persona's fixture, or their own sign-up record."""
    data = demo_data()
    if account.member_id in data.members:
        return data.members[account.member_id]
    return Member(member_id=account.member_id, display_name=account.name, renewal_date=account.renewal_date)


# ── documents: per member, kept in the session (demo personas start with their fixture documents) ──
def documents(member_id: str) -> dict[str, list]:
    store = st.session_state.setdefault("documents", {})
    if member_id not in store:
        data = demo_data()
        store[member_id] = {"notes": list(data.notes.get(member_id, [])),
                            "earnings": list(data.documents.get(member_id, []))}
    return store[member_id]


def add_note(member_id: str, note: ClinicalNote) -> None:
    documents(member_id)["notes"].append(note)


def add_earnings(member_id: str, docs: list[EarningsDocument]) -> None:
    """Hook for app/upload.py: earnings documents added here are included in the member's status."""
    known = {d.doc_id for d in documents(member_id)["earnings"]}
    documents(member_id)["earnings"].extend(d for d in docs if d.doc_id not in known)


def _fingerprint(member: Member, notes: list, earnings: list, live: bool) -> str:
    h = hashlib.sha256(member.model_dump_json().encode())
    for item in [*notes, *earnings]:
        h.update(item.model_dump_json().encode())
    h.update(b"live" if live else b"offline")
    return h.hexdigest()


def view_for(member: Member, live: bool) -> MemberView:
    """Run the pipeline on this member's own documents. Cached per content, so reruns don't re-call the LLM."""
    docs = documents(member.member_id)
    key = _fingerprint(member, docs["notes"], docs["earnings"], live)
    cache = st.session_state.setdefault("view_cache", {})
    if key not in cache:
        llm, _ = llm_for(live)
        with st.spinner("Checking your documents…"):
            cache[key] = build_view(member, docs["notes"], docs["earnings"], llm, FRAILTY, WALLET,
                                    demo_data().today)
    return cache[key]
