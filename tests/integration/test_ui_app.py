"""Headless smoke test of the Streamlit app (no browser): every persona renders with no exceptions."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(Path(__file__).resolve().parents[2] / "app" / "main.py")
EXPECTED = {"SYN-0001": "protected", "SYN-0002": "protected", "SYN-0003": "protected",
            "SYN-0004": "at risk", "SYN-0005": "at risk"}


def run(member_id=None, theme=None):
    at = AppTest.from_file(APP, default_timeout=60)
    if member_id:
        at.session_state["member_id"] = member_id
    at.run()
    if theme:
        at.radio[0].set_value(theme).run()
    return at


@pytest.mark.parametrize("member_id,word", EXPECTED.items())
def test_every_persona_renders_its_status(member_id, word):
    at = run(member_id)
    assert not at.exception, at.exception
    page = " ".join(m.value for m in at.markdown)
    assert f"is {word}" in page
    assert any("MassHealth makes all eligibility determinations" in c.value for c in at.caption)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_theme_switch_renders(theme):
    assert not run("SYN-0001", theme).exception


def test_red_team_persona_shows_ignored_injection_and_unchanged_result():
    at = run("SYN-0005")
    texts = " ".join(t.value for t in at.text)
    assert "Ignored in" in texts and "not 200 hours" in texts


def test_coach_answers_offline_from_a_suggested_question():
    at = run("SYN-0004")
    at.button(key="suggested-0").click().run()
    assert not at.exception, at.exception
    assert len(at.chat_message) >= 2
