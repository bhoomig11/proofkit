"""Coverage Coach widget: a chat dock in the bottom-right corner, like a messaging dock.

Closed, it is a slim bar docked to the bottom-right edge. Clicking it opens a chat box anchored to the
same corner. The page underneath never moves and stays usable. Minimize keeps the conversation; close
also clears it. On small screens the open chat becomes a full-screen sheet.

Self-contained on purpose, so the Coverage Coach can be owned end to end, separately from the dashboard:
  - UI shell (dock bar, chat box, header, open/close state, CSS, focus script): this file
  - chat body (messages, suggestions, settings, trace, read-aloud): app/agent_panel.py
  - brain (routing, read-only tools, wording): src/proofkit/integration/coach.py
main.py only calls `render_coach_widget(...)` once, after the page content.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.agent_panel import ChatBackend, render_agent_panel, render_settings
from proofkit.common.llm import LLMClient
from proofkit.wallet import WalletRules

OPEN_KEY = "coach_open"
FOCUS_KEY = "coach_focus"  # set for one run after open/minimize/close so focus follows the user
DOCK_WIDTH = "380px"
DOCK_RIGHT = "24px"
CHAT_HEIGHT = 340  # px; the message list scrolls inside the box (full height on phones, see CSS)

# Hide a button's text but keep it as the accessible name (icon-only header buttons).
_VISUALLY_HIDDEN = ("position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;"
                    "clip:rect(0,0,0,0);white-space:nowrap;border:0")

# Static CSS only. `st.container(key=...)` gives each container a `st-key-<key>` class we can position.
WIDGET_CSS = f"""<style>
.stMainBlockContainer,.block-container{{padding-bottom:5rem}}
.st-key-coach_launcher{{position:fixed;right:{DOCK_RIGHT};bottom:0;z-index:1000;width:min(320px,calc(100vw - 2 * {DOCK_RIGHT}))!important}}
.st-key-coach_launcher .stButton,.st-key-coach_launcher button{{width:100%}}
.st-key-coach_launcher button{{justify-content:flex-start;gap:.5rem;min-height:48px;padding:.5rem 1rem;
  border-radius:12px 12px 0 0;border:1px solid var(--pk-border);border-bottom:0;background:var(--pk-surface);
  color:var(--pk-text);font-weight:700;box-shadow:0 -2px 14px rgba(0,0,0,.18)}}
.st-key-coach_launcher button:hover,.st-key-coach_launcher button:focus,.st-key-coach_launcher button:active{{
  border-color:var(--pk-accent)!important;color:var(--pk-text)!important;background:var(--pk-surface)!important}}
.st-key-coach_panel button:focus:not(:active),.st-key-coach_panel button:hover{{color:inherit}}
.st-key-coach_suggestions button:hover,.st-key-coach_suggestions button:focus{{color:var(--pk-accent)!important;
  border-color:var(--pk-accent)!important;background:var(--pk-bg)!important}}
.st-key-coach_panel [data-testid="stChatInput"]:focus-within,
.st-key-coach_panel [data-testid="stChatInput"] div:focus-within{{border-color:var(--pk-focus)!important}}
.st-key-coach_launcher button::after{{content:"\\25B4";margin-left:auto;font-size:1.1rem}}
.st-key-coach_panel{{position:fixed;right:{DOCK_RIGHT};bottom:0;z-index:1000;
  width:min({DOCK_WIDTH},calc(100vw - 2 * {DOCK_RIGHT}))!important;max-height:min(640px,calc(100vh - 16px));
  overflow-y:auto;gap:.5rem;padding:0 .75rem .75rem;background:var(--pk-surface);color:var(--pk-text);
  border:1px solid var(--pk-border);border-bottom:0;border-radius:12px 12px 0 0;
  box-shadow:0 -4px 24px rgba(0,0,0,.22)}}
.st-key-coach_panel [data-testid="stElementContainer"],.st-key-coach_panel .stButton,
.st-key-coach_panel [data-testid="stChatInput"],.st-key-coach_launcher [data-testid="stElementContainer"],
.st-key-coach_launcher .stButton{{width:100%!important;max-width:100%}}
.st-key-coach_header{{position:sticky;top:0;z-index:2;background:var(--pk-surface);margin:0 -.75rem;
  width:calc(100% + 1.5rem)!important;padding:.35rem .5rem .35rem .9rem;border-bottom:1px solid var(--pk-border);gap:0}}
.st-key-coach_header [data-testid="stHorizontalBlock"]{{gap:.15rem;align-items:center;flex-wrap:nowrap}}
.st-key-coach_header [data-testid="stColumn"]{{min-width:0}}
.st-key-coach_header [data-testid="stColumn"]:first-child{{flex:1 1 auto!important;width:auto!important}}
.st-key-coach_header [data-testid="stColumn"]:not(:first-child){{flex:0 0 44px!important;width:44px!important}}
.st-key-coach_header button{{border:0;background:transparent;padding:0;min-height:44px;min-width:44px;
  color:var(--pk-text)}}
.st-key-coach_header button:hover{{background:var(--pk-bg)}}
.st-key-coach_header button p{{{_VISUALLY_HIDDEN}}}
.st-key-coach_header [data-testid="stPopoverButton"] svg{{display:none}}
.pk-coach-title{{margin:0;font-size:1rem;font-weight:800;line-height:1.2}}
.pk-coach-sub{{margin:0;font-size:.8rem;color:var(--pk-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.pk-dot{{display:inline-block;width:.6rem;height:.6rem;border-radius:50%;margin-right:.35rem;
  border:1px solid var(--pk-border);vertical-align:middle}}
.pk-dot-on{{background:var(--pk-ok)}}.pk-dot-off{{background:var(--pk-muted)}}
.st-key-coach_suggestions{{flex-direction:row!important;flex-wrap:wrap;gap:.4rem}}
.st-key-coach_suggestions [data-testid="stElementContainer"],.st-key-coach_suggestions .stButton{{width:auto!important;flex:0 0 auto}}
.st-key-coach_suggestions button{{border-radius:999px;padding:.25rem .8rem;min-height:44px;
  border:1px solid var(--pk-accent);color:var(--pk-accent);background:transparent;font-weight:600}}
.st-key-coach_script{{display:none}}
@media (max-width:760px){{
  .st-key-coach_launcher{{right:16px;bottom:16px;width:56px!important}}
  .st-key-coach_launcher button{{justify-content:center;width:56px;height:56px;padding:0;border-radius:50%;
    border:0;background:var(--pk-accent);color:var(--pk-accent-text);box-shadow:0 6px 20px rgba(0,0,0,.3)}}
  .st-key-coach_launcher button::after{{content:none}}
  .st-key-coach_launcher button p{{{_VISUALLY_HIDDEN}}}
  .st-key-coach_panel{{inset:0;width:100vw!important;max-height:none;height:100dvh;border-radius:0;border:0}}
  .st-key-coach_panel [data-testid="stVerticalBlockBorderWrapper"]:has(> div > .st-key-coach_messages){{
    height:calc(100dvh - 150px)!important;max-height:none!important}}
}}
</style>"""

# Static script, run from a hidden same-origin component. It never reads or writes chat text; it only
# moves focus, scrolls the message list to the newest answer, and lets Escape minimize the chat.
_DOCK_SCRIPT = """<script>
(function () {
  const doc = window.parent.document;
  const action = %(action)s;
  const panel = doc.querySelector('.st-key-coach_panel');
  if (panel) {
    const list = panel.querySelector('.st-key-coach_messages');
    const scroller = list && (list.closest('[data-testid="stVerticalBlockBorderWrapper"]') || list);
    [list, scroller].forEach(el => { if (el) el.scrollTop = el.scrollHeight; });
  }
  if (action === 'open') {
    const box = doc.querySelector('.st-key-coach_panel textarea');
    if (box) box.focus();
  } else if (action === 'closed') {
    const bar = doc.querySelector('.st-key-coach_launcher button');
    if (bar) bar.focus();
  }
  // Re-bind on every run: a listener from an earlier, removed frame can no longer run.
  const host = window.parent;
  if (host.__pkCoachEscape) doc.removeEventListener('keydown', host.__pkCoachEscape);
  host.__pkCoachEscape = (event) => {
    if (event.key !== 'Escape' || doc.querySelector('[data-baseweb="popover"]')) return;
    const minimize = doc.querySelector('.st-key-coach_min_btn button');
    if (minimize) { event.preventDefault(); minimize.click(); }
  };
  doc.addEventListener('keydown', host.__pkCoachEscape);
})();
</script>"""


SETTING_DEFAULTS = {"coach_plain": True, "coach_show_tech": False}


def is_open(st: Any) -> bool:
    return bool(st.session_state.get(OPEN_KEY, False))


def keep_settings(st: Any) -> None:
    """Streamlit forgets a widget's value on runs where the widget is not drawn (chat minimized).
    Re-saving each value every run keeps the member's language and switches until they change them."""
    for key, default in SETTING_DEFAULTS.items():
        st.session_state[key] = st.session_state.get(key, default)


def dock_script(action: str, nonce: int) -> str:
    """The hidden dock script; `nonce` changes when the script must run again (new message, toggle)."""
    if action not in {"open", "closed", "none"}:
        raise ValueError("action must be open, closed or none")
    return f"<!-- {int(nonce)} -->" + _DOCK_SCRIPT % {"action": f"'{action}'"}


def _toggle(st: Any, *, open_: bool, clear: bool = False) -> None:
    st.session_state[OPEN_KEY] = open_
    st.session_state[FOCUS_KEY] = "open" if open_ else "closed"
    if clear:
        st.session_state["chat_messages"] = []


def _run_script(st: Any, action: str, nonce: int) -> None:
    import streamlit.components.v1 as components

    with st.container(key="coach_script"):
        components.html(dock_script(action, nonce), height=0)


def render_coach_widget(*, view: Any, llm: LLMClient, wallet_rules: WalletRules, today: date,
                        is_live: bool, live_requested: bool, backend: ChatBackend | None = None) -> None:
    """Coverage Coach dock. Closed: a slim bar in the bottom-right corner. Open: a chat box in that corner."""
    import streamlit as st

    st.markdown(WIDGET_CSS, unsafe_allow_html=True)
    keep_settings(st)
    focus = st.session_state.pop(FOCUS_KEY, "none")
    live_help = "Live AI on" if is_live else "Live AI off: answers use verified facts only"
    live_short = "Live AI on" if is_live else "Offline: verified facts only"

    if not is_open(st):
        with st.container(key="coach_launcher"):
            st.button("Coverage Coach", icon=":material/chat:", key="coach_open_btn",
                      help=f"Open chat: ask about your status, proof, or next step. {live_help}.",
                      on_click=_toggle, args=(st,), kwargs={"open_": True})
        if focus == "closed":
            _run_script(st, "closed", 0)
        return

    with st.container(key="coach_panel"):
        with st.container(key="coach_header"):
            title, gear, minimize, close = st.columns([6, 1, 1, 1], vertical_alignment="center")
            dot = "pk-dot-on" if is_live else "pk-dot-off"
            title.markdown(
                "<p class='pk-coach-title' role='heading' aria-level='2'>Coverage Coach</p>"
                f"<p class='pk-coach-sub' title='{live_help}'><span class='pk-dot {dot}' aria-hidden='true'></span>"
                f"{live_help if is_live else live_short}</p>",
                unsafe_allow_html=True)
            with gear.popover("Chat settings", icon=":material/settings:", help="Chat settings"):
                render_settings()
            minimize.button("Minimize chat", icon=":material/expand_more:", key="coach_min_btn",
                            help="Minimize (Esc). Your conversation is kept.",
                            on_click=_toggle, args=(st,), kwargs={"open_": False})
            close.button("Close chat", icon=":material/close:", key="coach_close_btn",
                         help="Close and clear this conversation",
                         on_click=_toggle, args=(st,), kwargs={"open_": False, "clear": True})
        if live_requested and not is_live:
            st.caption("No API key found, so Coverage Coach is running offline.")
        render_agent_panel(view=view, llm=llm, wallet_rules=wallet_rules, today=today, backend=backend,
                           chat_height=CHAT_HEIGHT)
        nonce = len(st.session_state.get("chat_messages", []))
        _run_script(st, "open" if focus == "open" else "none", nonce)
