"""Coverage Coach display: answers wrap, and dynamic text can never become HTML, a link, or a formula."""
from __future__ import annotations

from app.agent_panel import answer_html


def test_answer_html_wraps_long_text_in_one_block():
    out = answer_html("Your status: At risk. " * 20)
    assert out.startswith("<div class='pk-answer'")
    assert "white-space:normal" in out and "overflow-wrap:anywhere" in out
    assert out.count("<div") == 1 and out.endswith("</div>")


def test_answer_html_escapes_html_tags():
    out = answer_html("Am I covered? <script>alert(1)</script>")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out


def test_answer_html_neutralises_markdown_links_and_emphasis():
    out = answer_html("[click here](https://evil.example) **now** _please_ `code`")
    for raw in ("[", "](", "**", "_", "`"):
        assert raw not in out, raw
    assert "&#91;click here&#93;" in out


def test_answer_html_dollar_amounts_cannot_render_as_a_formula():
    out = answer_html("You are $60 short. We counted $520.")
    assert "$" not in out
    assert out.count("&#36;") == 2


def test_answer_html_keeps_line_breaks_without_blank_lines():
    out = answer_html("Line one.\n\nLine two.\r\nLine three.")
    assert "\n" not in out and "\r" not in out
    assert out.count("<br>") == 3


def test_app_shows_coach_answer_in_the_wrapping_block():
    import pytest
    pytest.importorskip("streamlit")
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app" / "main.py"), default_timeout=60)
    at.session_state["member_id"] = "SYN-0004"
    at.run()
    at.button(key="suggested-0").click().run()
    assert not at.exception, at.exception
    answers = [m.value for m in at.markdown if "pk-answer" in m.value]
    assert answers, "the coach answer should render in the wrapping block"
    assert "At risk" in answers[0] and "&#36;60" in answers[0]
