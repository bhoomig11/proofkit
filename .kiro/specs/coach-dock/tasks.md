# Tasks: Coverage Coach corner dock

Built in one Kiro CLI session (vibe mode), then recorded here. Tests were written alongside the code, not first.

- [x] 1. Dock shell: corner bar and corner chat box, page never pushed
  - `app/coach_widget.py` CSS and containers.
  - Tests: `test_widget_is_positioned_by_static_css`, `test_dock_is_anchored_bottom_right_and_never_pushes_the_page`.
  - Requirements: 1.1 to 1.4.
- [x] 2. Header: title, live-AI dot, gear popover, minimize, close
  - Test: `test_minimize_keeps_the_conversation_and_close_clears_it`.
  - Requirements: 2.1 to 2.3.
- [x] 3. Settings behind the gear, kept across minimize, no Session State warning
  - Test: `test_settings_survive_minimizing_the_chat`.
  - Requirements: 3.1 to 3.3.
- [x] 4. Chat body: greeting, chips before the first question, scrolling list, pinned input, same-run answers
  - Test: `test_suggestions_show_until_the_first_question`; existing coach UI tests still pass.
  - Requirements: 4.1 to 4.4.
- [x] 5. Compact read aloud with stop
  - Requirement: 4.5. Checked by hand in Chrome; no automated test (browser speech).
- [x] 6. Focus, auto-scroll and Escape script, restricted to fixed actions
  - Test: `test_dock_script_only_moves_focus_and_scroll`.
  - Requirements: 2.4, 4.4, 6.1, 6.5.
- [x] 7. Phone layout (760px and below)
  - Requirements: 5.1, 5.2. Checked in headless Chrome at 390x844; no automated test.
- [x] 8. Theme colours for hover and focus (no Streamlit red)
  - Requirement: 6.3. Checked in headless Chrome.
- [x] 9. Verify
  - `pytest -m "not live"`: all passed; ruff clean.
  - Headless Chrome over CDP at 1366x860 and 390x844: page width unchanged when open (1360px), focus lands in
    the input on open and on the bar after minimize, Escape minimizes, reopened chat keeps its messages.

Not done:
- [ ] 10. Voice input (microphone) through the browser's SpeechRecognition API.
- [ ] 11. A recorded Playwright MCP pass (the CDP check above was a one-off script outside the repo).
