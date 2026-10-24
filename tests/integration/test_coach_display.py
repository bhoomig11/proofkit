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
    at = open_coach()
    at.button(key="suggested-0").click().run()
    assert not at.exception, at.exception
    answers = [m.value for m in at.markdown if "pk-answer" in m.value and "At risk" in m.value]
    assert answers, "the coach answer should render in the wrapping block"
    assert "&#36;60" in answers[0]


def test_coach_reply_carries_the_validated_inputs():
    from proofkit.common.llm import FakeLLM
    from proofkit.integration import ask_coach
    from tests.integration.test_agent_panel import _context

    c = _context("SYN-0004", FakeLLM({"coach_route": {"tool": "what_if",
                                                      "args": {"month": "2027-02", "extra_income": "60"}}}))
    reply = ask_coach("What if I earn $60 more?", member=c.member, status=c.status, llm=c.llm,
                      wallet_rules=c.wallet_rules, today=c.today)
    assert reply.inputs == {"month": "2027-02", "extra_income": "60"}


def test_describe_inputs_is_plain_words():
    from app.agent_panel import describe_inputs

    assert describe_inputs("what_if", {"month": "2027-02", "extra_income": "60", "extra_hours": "10"}) == \
        "Your what-if: +$60.00 income and +10 hours in February 2027"
    assert describe_inputs("explain_month", {"month": "2027-01"}) == "Month asked about: January 2027"
    assert describe_inputs("explain_status", {}) is None


def _dev_what_if():
    at = open_coach()
    at.button(key="suggested-1").click().run()  # "What if I earn $60 more?"
    return at


def test_how_we_know_shows_inputs_and_hides_tech_details_by_default():
    at = _dev_what_if()
    assert not at.exception, at.exception
    assert any(e.label == "How we know this" for e in at.expander)
    page = " ".join(m.value for m in at.markdown) + " ".join(t.value for t in at.text)
    assert "Your what-if: +&#36;60.00 income" in page
    assert "Tool:" not in page


def test_show_how_the_ai_works_reveals_tool_and_fallback():
    at = _dev_what_if()
    at.toggle(key="coach_show_tech").set_value(True).run()
    texts = " ".join(t.value for t in at.text)
    assert "Tool: what_if" in texts and "Answered by:" in texts


def open_coach(member_id="SYN-0004"):
    """Signed in as a demo account, with the floating Coverage Coach panel open (like a member would)."""
    import pytest
    pytest.importorskip("streamlit")
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    from app.auth import DEMO_LOGINS, Account

    demo = next(x for x in DEMO_LOGINS if x["member_id"] == member_id)
    at = AppTest.from_file(str(Path(__file__).resolve().parents[2] / "app" / "main.py"), default_timeout=60)
    at.session_state["account"] = Account(name=demo["name"], email=demo["email"], member_id=member_id)
    at.run()
    at.button(key="coach_open_btn").click().run()
    return at


def test_apostrophes_quotes_and_ampersands_are_escaped_exactly_once():
    out = answer_html("Hi, I'm Coverage Coach. I can tell you whether you're covered & \"why\" #1.")
    assert "&#35;x27;" not in out and "&amp;#" not in out   # an entity must never be re-escaped
    assert out.count("&#x27;") == 2                         # I'm, you're
    assert "&amp;" in out and "&quot;why&quot;" in out and "&#35;1" in out


def test_an_internal_error_is_never_shown_to_the_member(monkeypatch):
    from app import agent_panel
    from proofkit.contracts import Member

    def broken(*args, **kwargs):
        return Member.model_validate({})  # a pydantic error, like stale cached data after a code reload
    monkeypatch.setattr(agent_panel, "ask_coach", broken)
    at = open_coach("SYN-0004")
    at.button(key="suggested-0").click().run()
    shown = " ".join(e.value for e in at.error)
    assert "validation error" not in shown.lower() and "pydantic" not in shown
    assert "couldn't answer that" in shown
