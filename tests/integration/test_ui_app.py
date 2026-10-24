"""Headless smoke tests of the Streamlit app (no browser): sign-in, demo profiles, new-user flow, every section."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.auth import DEMO_LOGINS, Account  # noqa: E402

APP = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
EXPECTED = {"SYN-0001": "protected", "SYN-0002": "protected", "SYN-0003": "protected",
            "SYN-0004": "at risk", "SYN-0005": "at risk"}
SECTIONS = ["Next steps", "Documents", "Why", "Evidence", "Hours & money", "Proof packet"]


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    """Sign-ups in tests go to a temp file, never app/accounts.generated.json."""
    import app.auth as auth
    monkeypatch.setattr(auth, "DEFAULT_STORE", tmp_path / "accounts.json")
    monkeypatch.setattr(auth.AccountStore.__init__, "__defaults__", (tmp_path / "accounts.json",))


def signed_in(member_id: str, theme: str | None = None) -> AppTest:
    demo = next(d for d in DEMO_LOGINS if d["member_id"] == member_id)
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["account"] = Account(name=demo["name"], email=demo["email"], member_id=member_id)
    at.run()
    if theme:
        at.radio(key="theme").set_value(theme).run()
    return at


def page_text(at: AppTest) -> str:
    return " ".join([m.value for m in at.markdown] + [t.value for t in at.text] + [c.value for c in at.caption]
                    + [i.value for i in at.info])


def go(at: AppTest, section: str) -> AppTest:
    at.radio(key="section").set_value(section).run()
    assert not at.exception, at.exception
    return at


def test_signed_out_shows_sign_in_and_one_click_demos():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    assert "Welcome to RenewRight" in page_text(at)
    assert {f"demo-{d['member_id']}" for d in DEMO_LOGINS} <= {b.key for b in at.button}


def test_one_click_demo_signs_in():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.button(key="demo-SYN-0001").click().run()
    assert not at.exception, at.exception
    assert "Maria (synthetic) is protected" in page_text(at)


def test_sign_in_with_demo_credentials_opens_the_dashboard():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signin_email").input("maria@example.com")
    at.text_input(key="signin_password").input("maria-demo-2027")
    next(b for b in at.button if b.label == "Sign in").click().run()
    assert not at.exception, at.exception
    assert "is protected" in page_text(at) and "Member ID: SYN-0001" in page_text(at)


def test_wrong_password_is_rejected():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signin_email").input("maria@example.com")
    at.text_input(key="signin_password").input("not-the-password")
    next(b for b in at.button if b.label == "Sign in").click().run()
    assert any("don't match" in e.value for e in at.error)
    assert "account" not in at.session_state


def test_new_account_gets_its_own_empty_profile_then_a_sample_note_protects_it():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signup_name").input("Rosa")
    at.text_input(key="signup_email").input("rosa@example.org")
    at.text_input(key="signup_password").input("a-long-pass-9")
    next(b for b in at.button if b.label == "Create account").click().run()
    assert not at.exception, at.exception
    text = page_text(at)
    assert "Rosa is at risk" in text and "Maria" not in text           # own record, never a demo person
    assert "Add your documents" in text and "Member ID: SYN-1001" in text
    # continue as the new user in a fresh session (AppTest can't replay the now-gone sign-up form widgets)
    rosa = at.session_state["account"]
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["account"] = rosa
    at.run()
    go(at, "Documents")
    next(b for b in at.button if "lupus" in b.label.lower()).click().run()
    assert not at.exception, at.exception
    assert "Rosa is protected" in page_text(at)


def test_sign_out_returns_to_sign_in():
    at = signed_in("SYN-0004")
    at.button(key="signout").click().run()
    assert "account" not in at.session_state and "Welcome to RenewRight" in page_text(at)


@pytest.mark.parametrize("member_id,word", EXPECTED.items())
def test_every_demo_dashboard_shows_its_status(member_id, word):
    at = signed_in(member_id)
    assert not at.exception, at.exception
    assert f"is {word}" in page_text(at)
    assert "MassHealth makes all eligibility determinations" in page_text(at)


@pytest.mark.parametrize("section", SECTIONS)
def test_every_section_renders_for_every_status(section):
    for member_id in ("SYN-0001", "SYN-0004"):
        go(signed_in(member_id), section)


def test_evidence_section_no_longer_crashes_and_highlights():
    at = go(signed_in("SYN-0002"), "Evidence")          # was UnboundLocalError: 'ex'
    assert "not counted" in page_text(at)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_switch_renders(theme):
    assert not signed_in("SYN-0001", theme).exception


def test_red_team_section_only_for_the_red_team_profile():
    assert signed_in("SYN-0004").radio(key="section").options == SECTIONS
    at = signed_in("SYN-0005")
    assert at.radio(key="section").options == SECTIONS + ["Red team"]
    text = page_text(go(at, "Red team"))
    assert "Ignored in" in text and "not 200 hours" in text


def test_user_menu_shows_account_details_and_status_circle():
    at = signed_in("SYN-0001")
    text = page_text(at)
    assert "maria@example.com" in text and "Member ID: SYN-0001" in text and "Status: Protected" in text
    assert "pk-dot-ok" in " ".join(m.value for m in at.markdown)
    assert "pk-dot-risk" in " ".join(m.value for m in signed_in("SYN-0004").markdown)


def test_uploaded_pay_statement_updates_a_new_users_own_status_end_to_end():
    from datetime import date
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["account"] = Account(name="Rosa", email="rosa@example.org", member_id="SYN-1001",
                                          renewal_date=date(2027, 3, 20))
    at.run()
    assert "Add your documents" in page_text(at)
    go(at, "Documents")
    load_keys = [b.key for b in at.button if b.key and b.key.startswith("ui_extras_load_SYN-1001_")]
    assert load_keys, "sample gallery should offer samples to load"
    for key in load_keys:                      # the CSV sample is processed offline (no AI) and kept
        at.button(key=key).click().run()
        assert not at.exception, at.exception
    assert "Add your documents" not in page_text(at)      # her status now comes from her own statements
    go(at, "Hours & money")
    assert len(at.get("progress")) >= 2                   # hours + income bars for at least one month
