# Design: Coverage Coach corner dock

## Structure

- `app/coach_widget.py`: the shell. Closed: `st.container(key="coach_launcher")` with one button. Open:
  `st.container(key="coach_panel")` with a header container (`coach_header`: title, `st.popover` gear,
  minimize, close), the chat body, and a hidden script container (`coach_script`).
- `app/agent_panel.py`: the chat body. `render_settings()` draws the three settings for the gear popover.
  `render_agent_panel(..., chat_height=340)` draws the messages in `st.container(height=..., key="coach_messages")`
  with an inline `st.chat_input` below it.

## Positioning (R1, R5)

Static CSS on the `st-key-<key>` classes Streamlit adds to keyed containers:

- `.st-key-coach_launcher` and `.st-key-coach_panel` are `position:fixed; right:24px; bottom:0`. The bar is
  320px wide; the box is `min(380px, 100vw - 48px)`, at most `min(640px, 100vh - 16px)` tall, rounded top corners.
- The old `.stApp:has(.st-key-coach_panel) .block-container{margin-right:...}` rule is removed, so nothing reflows.
- Streamlit sets element widths in pixels from the page width, so children of the dock get `width:100%`.
- Under 760px: the bar becomes a 56px round button (label visually hidden), the box `inset:0; height:100dvh`,
  and the message list's border wrapper grows to `calc(100dvh - 150px)`.

## State (R2, R3, R4)

- `coach_open` (bool) and `coach_focus` ("open" / "closed", consumed once) live in session state. Buttons use
  `on_click` callbacks, so one click is one run.
- Close also sets `chat_messages = []`.
- Settings: Streamlit drops a widget's value on any run where the widget is not drawn (chat minimized).
  `keep_settings()` re-saves `coach_language`, `coach_plain` and `coach_show_tech` every run, with their defaults
  set in session state, not via `value=`, which avoids the Session State warning.
- Questions: chips and the input (`on_submit`) only queue the text in `coach_pending`. The panel answers it before
  drawing, so the answer shows in the same run and the chips disappear immediately (no `st.rerun()`).

## Focus, scroll, Escape (R2.2, R2.4, R4.4, R6.1, R6.5)

A hidden `components.html(..., height=0)` iframe is same-origin (Streamlit sandboxes it with
`allow-same-origin allow-scripts`), so its static script can reach `window.parent.document`. It:

- scrolls `.st-key-coach_messages` and its scroll wrapper to the bottom,
- focuses the chat textarea on "open" or the bar on "closed",
- re-binds one `keydown` listener on every run (a listener from a removed iframe can no longer run) that clicks
  minimize on Escape unless a popover is open.

`dock_script(action, nonce)` only accepts "open", "closed" or "none". The nonce (message count) changes the
iframe's HTML so the script runs again after each new message.

## Read aloud (R4.5)

The per-answer `speechSynthesis` iframe becomes a 44px text link. A second press calls `speechSynthesis.cancel()`.
It takes its colour from the parent's `--pk-accent`.

## Trade-offs

- Every click is a server round trip in Streamlit, so open and minimize take a fraction of a second; there is no
  slide animation. A custom component would avoid that, at much higher cost.
- The dock CSS relies on Streamlit 1.39 test IDs (`stElementContainer`, `stVerticalBlockBorderWrapper`,
  `stPopoverButton`). A Streamlit upgrade needs a visual re-check.
