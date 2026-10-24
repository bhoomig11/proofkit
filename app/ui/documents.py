"""Documents section: the member's clinical notes (upload or load a sample) and pay statements (Karthik's hook)."""
from __future__ import annotations

import streamlit as st

from app.format import long_date
from app.profile import ProfileError, note_from_upload, sample_notes
from app.ui import extras
from app.ui.common import add_note, demo_data, documents


def render_documents(member, wallet_rules, today, live: bool) -> None:
    docs = documents(member.member_id)
    st.markdown("### Your documents")
    if not live:
        st.caption("Live AI is off: RenewRight can read the sample documents below. Turn on Live AI in the "
                   "Accessibility menu to read your own.")

    notes_col, pay_col = st.columns(2, gap="large")
    with notes_col:
        st.markdown("#### Clinical notes")
        st.caption("Visit notes from your doctor or clinic, as plain text. Used to find a medical exemption.")
        for note in docs["notes"]:
            st.text(f"• {note.note_id} · {long_date(note.note_date)} · {len(note.text)} characters")
        with st.form("note_upload", clear_on_submit=True, border=False):
            upload = st.file_uploader("Add a note (.txt)", type=["txt"], key="note_file")
            visit = st.date_input("Visit date", value=today, max_value=today, key="note_date", format="MM/DD/YYYY")
            add = st.form_submit_button("Add note", type="primary")
        if add and upload is not None:
            try:
                add_note(member.member_id, note_from_upload(member, upload.name, upload.getvalue(), visit,
                                                            index=len(docs["notes"]) + 1))
                st.rerun()
            except ProfileError as exc:
                st.error(str(exc))
        with st.expander("Use a sample note"):
            for i, sample in enumerate(sample_notes(demo_data())):
                if st.button(sample.label, key=f"sample-note-{i}", use_container_width=True):
                    add_note(member.member_id, note_from_upload(member, sample.filename, sample.text.encode(),
                                                                sample.note_date, index=len(docs["notes"]) + 1))
                    st.rerun()

    with pay_col:
        st.markdown("#### Pay statements")
        st.caption("Earnings from your gig apps or jobs. Used to check 80 hours or $580 a month.")
        for doc in docs["earnings"]:
            st.text(f"• {doc.filename} ({doc.doc_type.value})")
        extras.earnings_upload(member, wallet_rules, today)
        extras.sample_gallery(member.member_id)
