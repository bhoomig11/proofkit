"""Extensible Coverage Coach backend and Streamlit chat panel."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from pydantic import ValidationError

from proofkit.common.llm import LLMClient
from proofkit.contracts import FindingsBundle, Member, ProofKitStatus
from proofkit.integration import ask_coach, welcome_message
from proofkit.wallet import WalletRules

from app.format import format_money, month_long
from app.highlight import escape_plain

SUGGESTED_QUESTIONS = (
    "Am I covered?",
    "What if I earn $60 more?",
    "What should I do next?",
)
LANGUAGE_OPTIONS = {"EN": "en", "ES": "es", "PT": "pt", "HT": "ht"}
VOICE_TAGS = {"en": "en-US", "es": "es-US", "pt": "pt-BR"}  # browsers have no Haitian Creole voice or recognizer
PENDING_KEY = "coach_pending"  # a chip or typed question waiting to be answered on the next run
INPUT_KEY = "coach_input"


@dataclass(frozen=True)
class CoachContext:
    member: Member
    status: ProofKitStatus
    findings: FindingsBundle | None
    wallet_rules: WalletRules
    today: date
    language: str
    plain: bool
    llm: LLMClient


@dataclass(frozen=True)
class ChatResult:
    answer: str
    tool: str
    facts: tuple[str, ...]
    used_fallback: bool
    disclaimer: str
    inputs: tuple[tuple[str, str], ...] = ()


class ChatBackend(Protocol):
    """Small extension point: a new agent needs only this method."""

    def ask(self, question: str, context: CoachContext) -> ChatResult:
        ...


class CoachBackend:
    """Default adapter over ProofKit's safe, read-only Coverage Coach."""

    def ask(self, question: str, context: CoachContext) -> ChatResult:
        reply = ask_coach(
            question,
            member=context.member,
            status=context.status,
            llm=context.llm,
            wallet_rules=context.wallet_rules,
            today=context.today,
            findings=context.findings,
            language=context.language,
            plain=context.plain,
        )
        return ChatResult(
            answer=reply.answer,
            tool=reply.tool,
            facts=tuple(reply.facts),
            used_fallback=reply.used_fallback,
            disclaimer=reply.disclaimer,
            inputs=tuple(reply.inputs.items()),
        )


def describe_inputs(tool: str, inputs: dict[str, str]) -> str | None:
    """Plain words for what the coach worked out, e.g. 'Your what-if: +$60.00 income in February 2027'."""
    from decimal import Decimal

    month = f" in {month_long(inputs['month'])}" if inputs.get("month") else ""
    if tool == "what_if":
        parts = ([f"+{format_money(Decimal(inputs['extra_income']))} income"] if inputs.get("extra_income") else []) \
            + ([f"+{inputs['extra_hours']} hours"] if inputs.get("extra_hours") else [])
        return f"Your what-if: {' and '.join(parts)}{month}" if parts else None
    if tool == "explain_month" and inputs.get("month"):
        return f"Month asked about: {month_long(inputs['month'])}"
    return None


# Characters Streamlit's markdown would act on: links, emphasis, code, headings, tables, and $...$ formulas.
_MARKDOWN_ENTITIES = {c: f"&#{ord(c)};" for c in "[]()*_`#|~$\\"}


def answer_html(text: str, lang: str | None = None, announce: bool = False) -> str:
    """Wrap dynamic coach text in one wrapping block that renders as plain characters.

    HTML is escaped, markdown and formula characters become entities, and line breaks become <br> so the
    block has no blank lines (a blank line would end the HTML block and let markdown run again).
    `lang` tells screen readers which language to read; `announce` marks the newest answer as a live region.
    """
    # One pass, one escape per character: escaping HTML first and then markdown would re-escape the '#'
    # inside entities like &#x27; and show the raw code instead of an apostrophe.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    safe = "".join(_MARKDOWN_ENTITIES.get(c) or escape_plain(c) for c in text).replace("\n", "<br>")
    attrs = (f" lang='{lang}'" if lang in LANGUAGE_OPTIONS.values() else "") \
        + (" role='status' aria-live='polite'" if announce else "")
    return f"<div class='pk-answer'{attrs} style='white-space:normal;overflow-wrap:anywhere'>{safe}</div>"


def answer_language(result: ChatResult, selected: str) -> str:
    """The language the answer is really in: offline answers are the English facts, whatever was selected."""
    return "en" if result.answer == " ".join(result.facts) else selected


def _safe_json_string(value: str) -> str:
    """Encode browser-script data without allowing an HTML closing tag."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _voice_input_html(language: str) -> str:
    """A mic button: the browser turns speech into text and puts it in the chat box for the member to check.
    It never sends by itself. Chrome's recognizer sends the audio to Google to transcribe it."""
    tag = _safe_json_string(VOICE_TAGS[language])
    return f"""<!doctype html><html><body style="margin:0;background:transparent;font-family:sans-serif">
<button id="mic" aria-label="Speak your question" title="Speak your question" aria-pressed="false"
 style="width:44px;height:44px;padding:0;border:0;border-radius:50%;background:transparent;color:#888;cursor:pointer">
<svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true"><path
 d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/>
</svg></button>
<span id="note" role="status" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)"></span>
<script>
const language={tag}; const button=document.getElementById('mic'); const note=document.getElementById('note');
const host=window.parent; const Recognition=host.SpeechRecognition || host.webkitSpeechRecognition;
let idle = '#888', active = '#5032C8';
try {{ const css = host.getComputedStyle(host.document.documentElement);
  idle = css.getPropertyValue('--pk-text').trim() || idle; active = css.getPropertyValue('--pk-accent').trim() || active;
}} catch (e) {{}}
button.style.color = idle;
function say(words) {{ note.textContent = words; button.title = words; }}
if (!Recognition) {{ button.disabled = true; button.style.opacity = '.4'; say('Voice input needs Chrome, Edge or Safari.'); }}
button.addEventListener('click', () => {{
  const box = host.document.querySelector('.st-key-coach_panel textarea');
  if (!box || !Recognition) return;
  const listen = new Recognition(); listen.lang = language; listen.interimResults = false;
  listen.onstart = () => {{ button.setAttribute('aria-pressed','true'); button.style.color = active; say('Listening...'); }};
  listen.onerror = () => {{ say('Sorry, I could not hear that. Try again, or type.'); }};
  listen.onend = () => {{ button.setAttribute('aria-pressed','false'); button.style.color = idle; }};
  listen.onresult = (event) => {{
    // React owns the box's value: set it through the native setter, then tell React it changed.
    const setValue = Object.getOwnPropertyDescriptor(host.HTMLTextAreaElement.prototype, 'value').set;
    setValue.call(box, event.results[0][0].transcript);
    box.dispatchEvent(new host.Event('input', {{bubbles: true}}));
    box.focus(); say('Check the words, then press Enter.');
  }};
  listen.start();
}});
</script></body></html>"""


def _read_aloud_html(answer: str, language: str) -> str:
    """A compact read-aloud control. Pressing it again while speaking stops the voice."""
    text = _safe_json_string(answer)
    tag = _safe_json_string(VOICE_TAGS[language])
    return f"""<!doctype html><html><body style="margin:0;background:transparent;font-family:sans-serif">
<button id="speak" aria-label="Read this answer aloud" aria-pressed="false"
 style="min-height:44px;padding:4px 10px;border:0;background:transparent;color:#5032C8;
 font-size:14px;font-weight:600;text-decoration:underline;cursor:pointer">&#128264; Read aloud</button>
<script>
const text={text}; const language={tag}; const button=document.getElementById('speak');
function idle() {{ button.textContent='\\u{{1F508}} Read aloud'; button.setAttribute('aria-pressed','false');
  button.setAttribute('aria-label','Read this answer aloud'); }}
try {{ const accent = window.parent.getComputedStyle(window.parent.document.documentElement)
  .getPropertyValue('--pk-accent').trim(); if (accent) button.style.color = accent; }} catch (e) {{}}
button.addEventListener('click', () => {{
  const speaking = button.getAttribute('aria-pressed') === 'true';
  window.speechSynthesis.cancel();
  if (speaking) {{ idle(); return; }}
  const speech = new SpeechSynthesisUtterance(text); speech.lang = language;
  speech.onend = idle; speech.onerror = idle;
  button.textContent='\\u{{23F9}} Stop reading'; button.setAttribute('aria-pressed','true');
  button.setAttribute('aria-label','Stop reading this answer');
  window.speechSynthesis.speak(speech);
}});
</script></body></html>"""


def render_settings() -> None:
    """Chat settings, shown behind the gear in the coach header. Values live in session state by key."""
    import streamlit as st

    st.toggle("Show how the AI works", key="coach_show_tech",
              help="Adds which read-only tool answered and whether live AI was used.")


def render_agent_panel(*, view: Any, llm: LLMClient, wallet_rules: WalletRules, today: date,
                       backend: ChatBackend | None = None, chat_height: int | None = None) -> None:
    """Render the Streamlit coach; imported lazily so pure tests do not need Streamlit.

    Settings are read from session state (the dock shows them behind its gear). `chat_height` puts the
    messages in a scrolling list of that height so the input stays pinned under it.
    """
    import streamlit as st
    import streamlit.components.v1 as components

    coach = backend or CoachBackend()
    language = "en"  # shortcut: language picker removed until offline answers are translated; restore it then
    plain = True  # answers are always plain language
    show_tech = bool(st.session_state.get("coach_show_tech", False))

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if st.session_state.get("chat_member") != view.member.member_id:
        st.session_state.chat_messages = []
        st.session_state.chat_member = view.member.member_id
        st.session_state.pop(PENDING_KEY, None)

    # Answer a chip or typed question before drawing, so the new message appears in this same run.
    question = st.session_state.pop(PENDING_KEY, None)
    if question:
        context = CoachContext(
            member=view.member,
            status=view.status,
            findings=view.findings,
            wallet_rules=wallet_rules,
            today=today,
            language=language,
            plain=plain,
            llm=llm,
        )
        try:
            st.session_state.chat_messages.append((question, coach.ask(question, context)))
        except ValidationError:  # an internal error (e.g. stale cached data after a code reload): never show it
            st.error("Sorry, I couldn't answer that just now. Please try again.")
        except ValueError as exc:  # the coach's own member-safe messages, e.g. a question that is too long
            st.error(str(exc))
    messages = st.session_state.chat_messages

    with st.container(key="coach_suggestions"):  # above the messages, so they stay in view for every question
        for index, label in enumerate(SUGGESTED_QUESTIONS):
            st.button(label, key=f"suggested-{index}", on_click=_queue, args=(label,))

    with st.container(height=chat_height, border=False, key="coach_messages"):
        if not messages:
            with st.chat_message("assistant"):
                st.markdown(answer_html(welcome_message(view.member)), unsafe_allow_html=True)
        for index, (asked, result) in enumerate(messages):
            with st.chat_message("user"):
                st.markdown(answer_html(asked), unsafe_allow_html=True)
            with st.chat_message("assistant"):
                _render_answer(result, language, components, st, show_tech, announce=index == len(messages) - 1)

    with st.container(key="coach_compose"):
        box, mic = st.columns([8, 1], vertical_alignment="center")
        with box:
            st.chat_input("Write a message...", key=INPUT_KEY, on_submit=_queue_typed)
        with mic:
            components.html(_voice_input_html(language), height=44)


def _queue(question: str) -> None:
    import streamlit as st

    st.session_state[PENDING_KEY] = question


def _queue_typed() -> None:
    import streamlit as st

    typed = st.session_state.get(INPUT_KEY)
    if typed:
        st.session_state[PENDING_KEY] = typed


def _render_answer(result: ChatResult, language: str, components: Any, st: Any, show_tech: bool = False,
                   announce: bool = False) -> None:
    """Render the answer, then 'How we know this': inputs and verified facts; tech details only on request."""
    spoken = answer_language(result, language)
    st.markdown(answer_html(result.answer, lang=spoken, announce=announce), unsafe_allow_html=True)
    if spoken != language:
        st.caption("Shown in English because live AI is off.")
    language = spoken  # read aloud with the voice that matches the text
    with st.expander("How we know this"):
        described = describe_inputs(result.tool, dict(result.inputs))
        if described:
            st.markdown(answer_html(described), unsafe_allow_html=True)
        st.caption("Checked by RenewRight's rules:")
        for fact in result.facts:
            st.markdown(answer_html(f"• {fact}"), unsafe_allow_html=True)
        if show_tech:
            st.text(f"Tool: {result.tool}")
            st.text("Answered by: " + ("rules only (live AI off or not used)" if result.used_fallback
                                       else "live AI wording over rule-checked facts"))
    if language == "ht":
        st.caption("Read aloud is unavailable: this browser may not have a Haitian Creole voice.")
    else:
        components.html(_read_aloud_html(result.answer, language), height=44)
