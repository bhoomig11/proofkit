"""Headless smoke tests of the Streamlit app (no browser): sign-in flow, every demo account's dashboard, coach."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from app.auth import DEMO_LOGINS, Account  # noqa: E402

APP = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
EXPECTED = {"SYN-0001": "protected", "SYN-0002": "protected", "SYN-0003": "protected",
            "SYN-0004": "at risk", "SYN-0005": "at risk"}


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
    return " ".join([m.value for m in at.markdown] + [t.value for t in at.text] + [c.value for c in at.caption])


def test_signed_out_shows_sign_in_and_demo_accounts():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception, at.exception
    assert "RenewRight" in page_text(at)
    assert "maria@example.com" in page_text(at)


def test_sign_in_with_demo_credentials_opens_the_dashboard():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signin_email").input("maria@example.com")
    at.text_input(key="signin_password").input("maria-demo-2027")
    at.button[0].click().run()          # the form's "Sign in" submit button
    assert not at.exception, at.exception
    assert "is protected" in page_text(at) and "Member ID: SYN-0001" in page_text(at)


def test_wrong_password_is_rejected():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signin_email").input("maria@example.com")
    at.text_input(key="signin_password").input("not-the-password")
    at.button[0].click().run()
    assert any("don't match" in e.value for e in at.error)
    assert "account" not in at.session_state


def test_new_account_sees_onboarding_then_example():
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="signup_name").input("Rosa")
    at.text_input(key="signup_email").input("rosa@example.com")
    at.text_input(key="signup_password").input("a-long-pass-9")
    next(b for b in at.button if b.label == "Create account").click().run()
    assert not at.exception, at.exception
    assert "Welcome, Rosa" in page_text(at)
    next(b for b in at.button if b.label.startswith("Explore an example")).click().run()
    assert "example member" in " ".join(i.value for i in at.info)


def test_sign_out_returns_to_sign_in():
    at = signed_in("SYN-0004")
    at.button(key="signout").click().run()
    assert "account" not in at.session_state and "maria@example.com" in page_text(at)


@pytest.mark.parametrize("member_id,word", EXPECTED.items())
def test_every_demo_account_dashboard_shows_its_status(member_id, word):
    at = signed_in(member_id)
    assert not at.exception, at.exception
    assert f"is {word}" in page_text(at)
    assert "MassHealth makes all eligibility determinations" in page_text(at)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_switch_renders(theme):
    assert not signed_in("SYN-0001", theme).exception


def test_red_team_account_shows_ignored_injection_and_unchanged_result():
    at = signed_in("SYN-0005")
    at.radio(key="section").set_value("Red team").run()
    text = page_text(at)
    assert "Ignored in" in text and "not 200 hours" in text


def test_nav_sections_switch_the_page_content():
    at = signed_in("SYN-0004")
    assert at.radio(key="section").options == ["Next steps", "Why", "Evidence", "Hours & money", "Proof packet", "Red team"]
    at.radio(key="section").set_value("Hours & money").run()
    assert not at.exception, at.exception
    assert any("Extra income" in s.label for s in at.slider)


def test_user_menu_shows_account_details_and_status_circle():
    at = signed_in("SYN-0001")
    text = page_text(at)
    assert "maria@example.com" in text and "Member ID: SYN-0001" in text and "Status: Protected" in text
    assert "pk-dot-ok" in " ".join(m.value for m in at.markdown)
    at_risk = signed_in("SYN-0004")
    assert "pk-dot-risk" in " ".join(m.value for m in at_risk.markdown)

