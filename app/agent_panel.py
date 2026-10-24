"""Extensible Coverage Coach backend and Streamlit chat panel."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

from proofkit.common.llm import LLMClient
from proofkit.contracts import FindingsBundle, Member, ProofKitStatus
from proofkit.integration import ask_coach
from proofkit.wallet import WalletRules

from app.format import format_money, month_long
from app.highlight import escape_plain

SUGGESTED_QUESTIONS = (
    "Am I covered?",
    "Why?",
    "What if I earn $60 more?",
    "What should I do next?",
)
LANGUAGE_OPTIONS = {"EN": "en", "ES": "es", "PT": "pt", "HT": "ht"}


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
    safe = escape_plain(text.replace("\r\n", "\n").replace("\r", "\n"))
    safe = "".join(_MARKDOWN_ENTITIES.get(c, c) for c in safe).replace("\n", "<br>")
    attrs = (f" lang='{lang}'" if lang in LANGUAGE_OPTIONS.values() else "") \
        + (" role='status' aria-live='polite'" if announce else "")
    return f"<div class='pk-answer'{attrs} style='white-space:normal;overflow-wrap:anywhere'>{safe}</div>"


def answer_language(result: ChatResult, selected: str) -> str:
    """The language the answer is really in: offline answers are the English facts, whatever was selected."""
    return "en" if result.answer == " ".join(result.facts) else selected


def _safe_json_string(value: str) -> str:
    """Encode browser-script data without allowing an HTML closing tag."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _read_aloud_html(answer: str, language: str) -> str:
    language_tags = {"en": "en-US", "es": "es-US", "pt": "pt-BR"}
    text = _safe_json_string(answer)
    tag = _safe_json_string(language_tags[language])
    return f"""<!doctype html><html><body style="margin:0;background:transparent">
<button id="speak" aria-label="Read this answer aloud" style="min-height:44px;padding:8px 12px">Read aloud</button>
<script>
const text={text}; const language={tag};
document.getElementById('speak').addEventListener('click', () => {{
  window.speechSynthesis.cancel();
  const speech = new SpeechSynthesisUtterance(text); speech.lang = language;
  window.speechSynthesis.speak(speech);
}});
</script></body></html>"""


def render_agent_panel(*, view: Any, llm: LLMClient, wallet_rules: WalletRules, today: date,
                       backend: ChatBackend | None = None) -> None:
    """Render the Streamlit coach; imported lazily so pure tests do not need Streamlit."""
    import streamlit as st
    import streamlit.components.v1 as components

    coach = backend or CoachBackend()
    st.caption("Ask about your status, proof, or next step. The coach cannot change your result.")
    language_label = st.selectbox("Answer language", tuple(LANGUAGE_OPTIONS), key="coach_language")
    plain = st.toggle("Plain language", value=True, key="coach_plain")
    show_tech = st.toggle("Show how the AI works", value=False, key="coach_show_tech",
                          help="Adds which read-only tool answered and whether live AI was used.")
    language = LANGUAGE_OPTIONS[language_label]

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if st.session_state.get("chat_member") != view.member.member_id:
        st.session_state.chat_messages = []
        st.session_state.chat_member = view.member.member_id

    suggested: str | None = None
    for index, label in enumerate(SUGGESTED_QUESTIONS):
        if st.button(label, key=f"suggested-{index}", use_container_width=True):
            suggested = label

    messages = st.session_state.chat_messages
    for index, (question, result) in enumerate(messages):
        with st.chat_message("user"):
            st.markdown(answer_html(question), unsafe_allow_html=True)
        with st.chat_message("assistant"):
            _render_answer(result, language, components, st, show_tech, announce=index == len(messages) - 1)

    question = suggested or st.chat_input("Ask Coverage Coach")
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
            result = coach.ask(question, context)
        except ValueError as exc:
            st.error(str(exc))
            return
        st.session_state.chat_messages.append((question, result))
        st.rerun()


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
        components.html(_read_aloud_html(result.answer, language), height=54)
