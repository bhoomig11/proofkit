"""New-user profiles: own synthetic record, note uploads, status from their own documents."""
from datetime import date
from pathlib import Path

import pytest

from app.data import load_demo_data
from app.profile import (MAX_NOTE_BYTES, ProfileError, new_member, next_member_id, note_from_upload,
                         sample_notes)
from app.state import build_view, make_llm
from proofkit.contracts import OverallStatus

ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2027, 3, 1)


def test_new_member_ids_start_at_1001_and_never_collide():
    assert next_member_id([]) == "SYN-1001"
    assert next_member_id(["SYN-0001", "SYN-1001", "SYN-1007"]) == "SYN-1008"
    m = new_member("Rosa Diaz", date(2027, 6, 30), ["SYN-1001"])
    assert m.member_id == "SYN-1002" and m.display_name == "Rosa Diaz" and m.renewal_date == date(2027, 6, 30)


def test_empty_profile_is_at_risk_with_actions_not_someone_else():
    llm, _ = make_llm(live=False, data=load_demo_data(ROOT))
    member = new_member("Rosa", date(2027, 6, 30), [])
    view = build_view(member, [], [], llm, ROOT / "config/frailty_rules.json", ROOT / "config/wallet_rules.json", TODAY)
    assert view.member.display_name == "Rosa"
    assert view.status.status == OverallStatus.AT_RISK and view.status.action_items
    assert view.exemption is None and view.wallet is None and view.findings.findings == []


def test_note_upload_becomes_the_users_own_clinical_note():
    member = new_member("Rosa", date(2027, 6, 30), [])
    note = note_from_upload(member, "visit.txt", b"Assessment: active SLE with nephritis.", date(2027, 1, 5), index=1)
    assert note.member_id == member.member_id and note.note_id == f"N-{member.member_id[4:]}-u1"
    assert note.text.startswith("Assessment") and note.note_date == date(2027, 1, 5)


@pytest.mark.parametrize("content,why", [(b"", "empty"), (b"\xff\xfe\x00bad", "not text"),
                                         (b"x" * (MAX_NOTE_BYTES + 1), "too large")])
def test_bad_note_uploads_are_rejected(content, why):
    with pytest.raises(ProfileError):
        note_from_upload(new_member("Rosa", date(2027, 6, 30), []), "n.txt", content, TODAY, index=1)


def test_sample_note_works_offline_and_gives_the_new_user_an_exemption():
    data = load_demo_data(ROOT)
    llm, _ = make_llm(live=False, data=data)
    member = new_member("Rosa", date(2027, 3, 20), [])
    samples = sample_notes(data)
    lupus = next(s for s in samples if "lupus" in s.label.lower())
    note = note_from_upload(member, lupus.filename, lupus.text.encode(), lupus.note_date, index=1)
    view = build_view(member, [note], [], llm, ROOT / "config/frailty_rules.json", ROOT / "config/wallet_rules.json", TODAY)
    assert view.status.status == OverallStatus.PROTECTED
    assert view.status.member_id == member.member_id     # the user's own record, not Maria's
