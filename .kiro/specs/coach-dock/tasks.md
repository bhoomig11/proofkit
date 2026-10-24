# Tasks: coach-dock

Recorded after the code (see the provenance note in `requirements.md`). Tests were written alongside the code,
not first. Requirement and property numbers refer to `requirements.md` and `design.md`.

## Dock (Kiro CLI session on `final/chatbot-ui`, then `746e9a3` on `main`)

- [x] 1. Corner dock shell: bar and chat box fixed to the bottom-right corner; remove the page-push rule
  - Properties P1 to P3. Requirements R1.
- [x] 2. Header: title, live/offline dot, gear popover, minimize, close; Escape minimizes
  - Property P4. Requirements R2.
- [x] 3. Settings behind the gear, kept while minimized, with no Session State warning (`keep_settings`)
  - Property P5. Requirements R3.4.
- [x] 4. Chat body: scrolling message list, composer pinned below, chip or typed question answered in the same run
  - Requirements R4.3, R4.4.
- [x] 5. Compact read aloud that stops on a second press
  - Requirements R5.4. Browser-only; checked by hand.
- [x] 6. Dock script for focus, auto-scroll and Escape, restricted to fixed actions
  - Property P12. Requirements R7.1, R8.1, R8.2.
- [x] 7. Phone layout: round button, full-screen chat
  - Requirements R6. Browser-only; checked in headless Chrome at 390x844.
- [x] 8. Theme colours for hover and focus instead of Streamlit red
  - Requirements R7.3. Checked in headless Chrome.
- [x] 9. Verify the dock
  - The full non-live suite passed and ruff was clean on `63f42bb`.
  - Headless Chrome over the DevTools protocol (a one-off script outside the repo), at 1366x860:
    - the page stayed 1360px wide with the chat open;
    - focus landed in the message box on open, and on the bar after minimize;
    - Escape minimized, and the reopened chat kept its messages.
  - At 390x844: a 56px round button; the chat filled the screen.

## Follow-ups on `main` (Arsh, PR #5)

- [x] 10. Opening line that cannot crash on a blank name and uses only a trusted first name (`470f824`)
  - Property P9. Requirements R4.1.
- [x] 11. Chips stay on top for every question; speak a question with the mic (`0774d4b`)
  - Properties P8, P11. Requirements R4.2, R5.1 to R5.3.
- [x] 12. Remove the answer-language picker until offline answers are translated (`298a100`)
  - Property P7. Requirements R3.3.
- [x] 13. Mic icon beside the message box; remove the plain-language toggle (`656da8e`)
  - Property P6. Requirements R3.1, R3.2, R5.1.
- [x] 14. Never show internal errors in the chat; drop the "Why?" chip (`91b338b`)
  - Properties P8, P10. Requirements R4.2, R4.5, R4.6.
- [x] 15. Verify on `main`
  - 83 coach tests pass on `3b679fa` (`test_coach_widget`, `test_coach_a11y`, `test_coach_display`,
    `test_coach_chat`, `test_coach_plain_facts`, `test_coach`, `test_agent_panel`).

## Not done

- [ ] 16. Translated offline answers, then bring back the language picker (R3.3) and non-English voices (R5).
- [ ] 17. A recorded Playwright MCP pass over the dock (`.kiro/settings/mcp.json` has Playwright), replacing the
  one-off headless Chrome check in task 9.
- [ ] 18. Automated browser tests for focus, Escape and the phone layout (R6, R7.1), which `AppTest` cannot see.
