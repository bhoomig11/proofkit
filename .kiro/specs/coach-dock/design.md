# Design: coach-dock

## Overview

Streamlit has no floating-widget primitive, so the dock is built from keyed containers plus static CSS.
`st.container(key=...)` adds a `st-key-<key>` class, and the CSS pins those containers to the corner. One small
hidden script handles what Streamlit cannot: focus, scroll position and the Escape key. Everything else is
ordinary Streamlit widgets with callbacks, so the existing `AppTest` suite can drive the dock.

```
main.py ── render_coach_widget(view, llm, ...)          app/coach_widget.py
             ├─ closed: coach_launcher ── [Coverage Coach ▴]
             └─ open:   coach_panel
                         ├─ coach_header   title · live dot · gear (popover) · minimize · close
                         ├─ render_agent_panel(chat_height=340)   app/agent_panel.py
                         │    ├─ coach_suggestions   3 chips (always on top)
                         │    ├─ coach_messages      st.container(height=340), scrolls
                         │    │    └─ opening line, then Q/A pairs, each with "How we know this" + Read aloud
                         │    └─ coach_compose       st.chat_input + mic iframe
                         └─ coach_script   hidden iframe: focus / scroll / Escape
```

## Components

### `app/coach_widget.py`

- `WIDGET_CSS`: static CSS only, no member data.
  - `.st-key-coach_launcher` and `.st-key-coach_panel` are `position:fixed; right:24px; bottom:0; z-index:1000`.
    The bar is 320px wide, and the box `min(380px, 100vw - 48px)`, at most `min(640px, 100vh - 16px)`.
  - The old `.stApp:has(.st-key-coach_panel) .block-container{margin-right:...}` push rule is removed. The main
    container gets `padding-bottom:5rem`, so the bar never covers the last line of the page.
  - Streamlit sizes element containers in pixels from the page width, so dock children get `width:100%`.
  - Icon-only header buttons hide their label with a visually-hidden rule, so screen readers still read it.
  - Under 760px: a 56px round accent button (label visually hidden), and the box becomes `inset:0; height:100dvh`.
- State in `st.session_state`:
  - `coach_open` (bool).
  - `coach_focus` ("open" or "closed"), set by the toggle callback and consumed once on the next run.
  - `chat_messages` (list of question and `ChatResult` pairs). Close empties it.
- `keep_settings()`: Streamlit drops a widget's value on any run where the widget is not drawn, which is the
  case while the chat is minimized. `SETTING_DEFAULTS = {"coach_show_tech": False}` is re-saved on every run.
  The default comes from session state, not `value=`, which avoids the "default value and Session State" warning.
- `dock_script(action, nonce)`: raises `ValueError` unless `action` is "open", "closed" or "none". The nonce is
  the message count; it changes the iframe's HTML so the script runs again after each new message.

### `app/agent_panel.py`

- `render_settings()`: the gear popover, with one toggle, `coach_show_tech`.
- `render_agent_panel(..., chat_height)`:
  - `language = "en"` and `plain = True`, fixed until offline answers are translated (`298a100`, `656da8e`).
  - Chips and `st.chat_input(on_submit=...)` only queue the text in `coach_pending`. The panel answers it before
    drawing anything, so the answer shows in the same run with no `st.rerun()`.
  - The opening line is `welcome_message(member)` from `proofkit.integration`, using the same trusted
    first-name rule as the coach's greeting (`470f824`).
  - Errors: `pydantic.ValidationError` (for example, stale cached data after a reload) shows a fixed apology.
    `ValueError` is the coach's own member-safe message and is shown as is (`91b338b`).
- `_voice_input_html(language)`: a mic button in a same-origin iframe beside the input. It uses the parent's
  `SpeechRecognition` or `webkitSpeechRecognition`, and sets the textarea through the native value setter plus an
  `input` event, so React sees the change. It never submits. A hidden `role="status"` span announces "Listening...",
  errors and "Check the words, then press Enter." The colours come from `--pk-text` and `--pk-accent`.
- `_read_aloud_html(answer, language)`: a 44px text link. The answer is JSON-encoded with `<`, `>` and `&` escaped,
  so it cannot close the script tag. A second press calls `speechSynthesis.cancel()`, and `aria-pressed` tracks the state.

## Dock script

The iframe from `components.html(..., height=0)` is same-origin: Streamlit sandboxes it with
`allow-same-origin allow-scripts`. That lets it reach `window.parent.document`. On each run it:

1. scrolls `.st-key-coach_messages` and its `stVerticalBlockBorderWrapper` to the bottom,
2. focuses the chat textarea ("open") or the bar button ("closed"),
3. re-binds one `keydown` listener on the parent document. A listener created by an earlier, removed iframe can no
   longer run, so it is removed and replaced each time. Escape clicks `.st-key-coach_min_btn button`, unless a
   `[data-baseweb="popover"]` is open.

## Correctness properties

| # | Property | Requirements | Test |
|---|---|---|---|
| P1 | Closed by default: open button only, no chat input | R1.3 | `test_closed_by_default_shows_only_the_launcher` |
| P2 | Open and close toggle the chat input | R1, R2 | `test_launcher_opens_the_panel_and_close_hides_it` |
| P3 | Bar and box anchored bottom-right; no page reflow rule | R1.1, R1.2 | `test_widget_is_positioned_by_static_css`, `test_dock_is_anchored_bottom_right_and_never_pushes_the_page` |
| P4 | Minimize keeps messages; close clears them | R2 | `test_minimize_keeps_the_conversation_and_close_clears_it` |
| P5 | Setting survives minimize, with no Session State warning | R3 | `test_settings_survive_minimizing_the_chat` |
| P6 | Only "Show how the AI works" in settings; no plain toggle | R3 | `test_settings_only_offer_how_the_ai_works` |
| P7 | No language picker; answers tagged `lang='en'` | R3, R7 | `test_no_language_picker_for_now_and_answers_are_tagged_english` |
| P8 | Exactly the three chips, still on top after a question | R4 | `test_suggestions_are_the_three_questions_with_useful_answers`, `test_suggestions_stay_on_top_after_a_question` |
| P9 | Opening line uses only a trusted first name | R4 | `test_opening_message_uses_the_first_name_when_known`, `test_opening_message_leaves_out_a_name_it_cannot_trust` |
| P10 | Internal errors never reach the member | R4 | `test_an_internal_error_is_never_shown_to_the_member` |
| P11 | Mic fills the box in the chosen language and never sends | R5, R8 | `test_voice_input_fills_the_chat_box_in_the_chosen_language_and_never_sends` |
| P12 | Dock script only focuses and scrolls; rejects any other action | R8 | `test_dock_script_only_moves_focus_and_scroll` |
| P13 | A typed jailbreak cannot change the status | R8 | `test_typed_question_gets_an_answer_and_cannot_change_status` |
| P14 | Newest answer is a polite live region | R7 | `test_latest_answer_is_announced_to_screen_readers` |

## Trade-offs and risks

- Every click is a Streamlit server round trip, so opening and minimizing take a fraction of a second, with no slide
  animation. A custom component would fix that at much higher cost.
- The CSS relies on Streamlit 1.39 test IDs (`stElementContainer`, `stVerticalBlockBorderWrapper`,
  `stPopoverButton`, `stChatInput`). A Streamlit upgrade needs a visual re-check.
- Chrome's speech recognizer sends audio to Google to transcribe it. The mic is opt-in per press and never sends
  the message; the docstring says so.
- The phone layout and the focus, scroll and Escape behaviour are browser-only, so `AppTest` cannot cover them. They
  were checked once in headless Chrome over the DevTools protocol (see tasks).
