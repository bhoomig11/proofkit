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
        )


# Characters Streamlit's markdown would act on: links, emphasis, code, headings, tables, and $...$ formulas.
_MARKDOWN_ENTITIES = {c: f"&#{ord(c)};" for c in "[]()*_`#|~$\\"}


def answer_html(text: str) -> str:
    """Wrap dynamic coach text in one wrapping block that renders as plain characters.

    HTML is escaped, markdown and formula characters become entities, and line breaks become <br> so the
    block has no blank lines (a blank line would end the HTML block and let markdown run again).
    """
    safe = escape_plain(text.replace("\r\n", "\n").replace("\r", "\n"))
    safe = "".join(_MARKDOWN_ENTITIES.get(c, c) for c in safe).replace("\n", "<br>")
    return f"<div class='pk-answer' style='white-space:normal;overflow-wrap:anywhere'>{safe}</div>"


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

    for question, result in st.session_state.chat_messages:
        with st.chat_message("user"):
            st.text(question)
        with st.chat_message("assistant"):
            _render_answer(result, language, components, st)

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


def _render_answer(result: ChatResult, language: str, components: Any, st: Any) -> None:
    """Render dynamic answer/facts as plain text and a transparent trace."""
    st.markdown(answer_html(result.answer), unsafe_allow_html=True)
    with st.expander("Agent trace — how this answer was made"):
        st.text(f"Tool: {result.tool}")
        st.text("Arguments: validated inside the read-only coach")
        st.text(f"Fallback used: {'yes' if result.used_fallback else 'no'}")
        st.text("Verified facts:")
        for fact in result.facts:
            st.markdown(answer_html(f"• {fact}"), unsafe_allow_html=True)
    if language == "ht":
        st.caption("Read aloud is unavailable: this browser may not have a Haitian Creole voice.")
    else:
        components.html(_read_aloud_html(result.answer, language), height=54)
