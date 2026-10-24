"""Coverage Coach accessibility: readable messages, announced answers, and the right language for screen
readers and read-aloud (offline answers are English even if another language is selected)."""
from app.agent_panel import ChatResult, answer_html, answer_language



def _result(answer, facts):
    return ChatResult(answer=answer, tool="explain_status", facts=tuple(facts), used_fallback=True, disclaimer="d")


def test_answer_html_sets_language_and_can_announce():
    out = answer_html("Hola", lang="es", announce=True)
    assert out.startswith("<div class='pk-answer'")
    assert "lang='es'" in out and "role='status'" in out and "aria-live='polite'" in out
    assert "role=" not in answer_html("Hi") and "lang=" not in answer_html("Hi")


def test_offline_facts_answer_is_english_even_when_spanish_is_selected():
    offline = _result("Your status: At risk.", ["Your status: At risk."])
    worded = _result("Su estado: en riesgo.", ["Your status: At risk."])
    assert answer_language(offline, "es") == "en"
    assert answer_language(worded, "es") == "es"


def _ask(selected_language="EN"):
    from tests.integration.test_coach_display import open_coach

    at = open_coach("SYN-0004")
    at.selectbox(key="coach_language").set_value(selected_language).run()
    at.button(key="suggested-0").click().run()
    return at


def test_questions_render_in_the_readable_wrapping_style():
    at = _ask()
    assert not at.exception, at.exception
    assert not any("Am I covered?" == t.value for t in at.text)
    assert any("pk-answer" in m.value and "Am I covered?" in m.value for m in at.markdown)


def test_latest_answer_is_announced_to_screen_readers():
    at = _ask()
    announced = [m.value for m in at.markdown if "role='status'" in m.value and "pk-answer" in m.value]
    assert len(announced) == 1 and "At risk" in announced[0]


def test_offline_spanish_selection_is_explained_and_tagged_english():
    at = _ask("ES")
    assert any("Shown in English because live AI is off" in c.value for c in at.caption)
    answer = next(m.value for m in at.markdown if "role='status'" in m.value and "pk-answer" in m.value)
    assert "lang='en'" in answer


def test_voice_input_fills_the_chat_box_in_the_chosen_language_and_never_sends():
    from app.agent_panel import _voice_input_html

    html = _voice_input_html("es")
    assert "SpeechRecognition" in html and '"es-US"' in html
    assert "innerHTML" not in html and ".click()" not in html and "submit" not in html.lower()
