"""Coverage Coach widget: a floating launcher (bottom-right) that opens a chat panel on the right edge.

Self-contained on purpose, so the Coverage Coach can be owned end to end, separately from the dashboard:
  - UI shell (launcher, panel, open/close state, CSS): this file
  - chat body (messages, suggestions, language, trace, read-aloud): app/agent_panel.py
  - brain (routing, read-only tools, wording): src/proofkit/integration/coach.py
main.py only calls `render_coach_widget(...)` once, after the page content.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.agent_panel import ChatBackend, render_agent_panel
from proofkit.common.llm import LLMClient
from proofkit.wallet import WalletRules

OPEN_KEY = "coach_open"
PANEL_WIDTH = "420px"

# Static CSS only. `st.container(key=...)` gives each container a `st-key-<key>` class we can position.
WIDGET_CSS = f"""<style>
.st-key-coach_launcher{{position:fixed;right:24px;bottom:24px;z-index:1000;width:auto!important}}
.st-key-coach_launcher button{{border-radius:999px;padding:.6rem 1.1rem;font-weight:700;
  box-shadow:0 6px 20px rgba(0,0,0,.25)}}
.st-key-coach_panel{{position:fixed;top:0;right:0;bottom:0;width:min({PANEL_WIDTH},100vw);z-index:1000;
  overflow-y:auto;padding:1rem 1rem 2rem;background:var(--pk-surface);color:var(--pk-text);
  border-left:1px solid var(--pk-border);box-shadow:-8px 0 24px rgba(0,0,0,.18)}}
.stApp:has(.st-key-coach_panel) .block-container{{margin-right:min({PANEL_WIDTH},100vw)}}
@media (max-width:760px){{.stApp:has(.st-key-coach_panel) .block-container{{margin-right:0}}}}
</style>"""


def is_open(st: Any) -> bool:
    return bool(st.session_state.get(OPEN_KEY, False))


def render_coach_widget(*, view: Any, llm: LLMClient, wallet_rules: WalletRules, today: date,
                        is_live: bool, live_requested: bool, backend: ChatBackend | None = None) -> None:
    """Floating Coverage Coach. Closed: a launcher button. Open: a right-side panel with the chat."""
    import streamlit as st

    st.markdown(WIDGET_CSS, unsafe_allow_html=True)
    if not is_open(st):
        with st.container(key="coach_launcher"):
            if st.button("Coverage Coach", icon=":material/chat:", key="coach_open_btn", type="primary",
                         help="Ask about your status, proof, or next step"):
                st.session_state[OPEN_KEY] = True
                st.rerun()
        return

    with st.container(key="coach_panel"):
        title, close = st.columns([5, 1], vertical_alignment="center")
        title.markdown("### Coverage Coach")
        if close.button("Close", icon=":material/close:", key="coach_close_btn", help="Close Coverage Coach"):
            st.session_state[OPEN_KEY] = False
            st.rerun()
        st.caption("Live AI on" if is_live else "Live AI off: answers use verified facts only")
        if live_requested and not is_live:
            st.caption("No API key found, so Coverage Coach is running offline.")
        render_agent_panel(view=view, llm=llm, wallet_rules=wallet_rules, today=today, backend=backend)
