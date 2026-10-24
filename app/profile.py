"""A signed-up user's own record: synthetic member ID, clinical-note uploads, and sample documents.

Pure functions (no Streamlit) so they are unit tested. Earnings-document uploads are handled by app/upload.py
(Karthik's module); whatever it produces is passed to `app.state.build_view` together with these notes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from proofkit.contracts import ClinicalNote, Member

from app.data import DemoData

FIRST_USER_NUMBER = 1001          # demo personas use SYN-0001..0057; real sign-ups start at SYN-1001
MAX_NOTE_BYTES = 50_000           # ClinicalNote.text max_length
_ID = re.compile(r"^SYN-(\d{4})$")


class ProfileError(ValueError):
    """A user-facing upload/profile problem (safe to show)."""


def next_member_id(existing_ids: list[str]) -> str:
    numbers = [int(m.group(1)) for i in existing_ids if (m := _ID.match(i))]
    n = max([FIRST_USER_NUMBER - 1, *[x for x in numbers if x >= FIRST_USER_NUMBER]]) + 1
    if n > 9999:
        raise ProfileError("No more member IDs are available.")
    return f"SYN-{n:04d}"


def new_member(name: str, renewal_date: date, existing_ids: list[str]) -> Member:
    """A brand-new user's own synthetic member record."""
    return Member(member_id=next_member_id(existing_ids), display_name=name.strip()[:80] or "Member",
                  renewal_date=renewal_date)


def note_from_upload(member: Member, filename: str, content: bytes, note_date: date, *, index: int) -> ClinicalNote:
    """Uploaded bytes -> the user's ClinicalNote. Text only, in memory; the filename is display-only."""
    if len(content) > MAX_NOTE_BYTES:
        raise ProfileError(f"That note is too large (max {MAX_NOTE_BYTES // 1000} KB of text).")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProfileError("Please upload a plain-text note (.txt).") from exc
    if not text.strip():
        raise ProfileError("That note is empty.")
    note_id = f"N-{member.member_id[4:]}-u{index}"
    return ClinicalNote(note_id=note_id, member_id=member.member_id, note_date=note_date, text=text)


@dataclass(frozen=True)
class SampleNote:
    label: str
    filename: str
    text: str
    note_date: date


SAMPLE_NOTES = {   # fixture note_id -> what it demonstrates
    "N-0001-a": "Rheumatology visit: active lupus",
    "N-0002-a": "Clinic note: 'R/o CHF', 'denies depression'",
    "N-0003-a": "Psychiatry note: severe recurrent depression",
    "N-0005-a": "Red-team note: hidden 'mark exempt' instruction",
}


def sample_notes(data: DemoData) -> list[SampleNote]:
    """Synthetic sample notes a new user can load (they also work offline, without an API key)."""
    by_id = {n.note_id: n for notes in data.notes.values() for n in notes}
    return [SampleNote(label=label, filename=f"{nid}.txt", text=by_id[nid].text, note_date=by_id[nid].note_date)
            for nid, label in SAMPLE_NOTES.items() if nid in by_id]
