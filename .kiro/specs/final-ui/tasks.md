# Tasks — ProofKit Coverage Copilot UI (2-hour timebox)

Tasks are ordered by demo risk. Each implementation task follows RED → GREEN → REFACTOR.
Do not begin stretch work until every P0/P1 task is green.

## P0 — Complete, deterministic demo path

- [x] 1. Build and test pure UI helpers
  - [ ] 1.1 RED: add failing unit/property tests for Decimal money formatting, long dates,
    countdown labels, month labels, protected-by copy, HTML/markdown-safe text, exact-offset
    quote highlighting, and theme contrast.
  - [ ] 1.2 GREEN: implement `app/format.py`, `app/highlight.py`, `app/a11y.py`, and
    `app/theme.py` with light/dark tokens, CSS accessibility toggles, and Pip SVG.
  - [ ] 1.3 REFACTOR: run focused helpers tests and ruff.
  - Requirements: 2, 4, 5, 14, 15, 17, 18.

- [x] 2. Build and test fixture loading + offline replay pipeline
  - [ ] 2.1 RED: test all five fixture personas can be loaded and processed offline to the
    expected status; assert SYN-0005 is At risk, 30h/$410, with no exemption.
  - [ ] 2.2 GREEN: implement `app/data.py`, `app/offline.py`, and framework-neutral
    `MemberView` / `build_member_view` in `app/state.py`; use public APIs only.
  - [ ] 2.3 REFACTOR: cache only in the Streamlit adapter; keep pipeline functions testable.
  - Requirements: 1, 10, 13, 17, 18.

- [x] 3. Build and test Coverage Coach adapter
  - [ ] 3.1 RED: test `ChatBackend` with `FakeLLM`: question appears only in
    `untrusted_text`; no-key fallback answers; trace includes the selected tool + verified facts;
    adversarial request cannot mutate SYN-0005 status.
  - [ ] 3.2 GREEN: implement `app/agent_panel.py` protocol/dataclasses, `CoachBackend`,
    suggested prompts, Streamlit rendering, honest trace, and safe read-aloud.
  - [ ] 3.3 REFACTOR: centralize tool/suggestion metadata and run focused tests.
  - Requirements: 6, 10, 12, 13, 16, 17, 18.

- [x] 4. Build and test escaped proof packet
  - [ ] 4.1 RED: test packet contents, exact disclaimer, highlighted quote, escaped script,
    monthly values, statement, and no unsafe dynamic HTML.
  - [ ] 4.2 GREEN: implement/export `proofkit.integration.build_packet_html`; keep it pure.
  - [ ] 4.3 REFACTOR: run integration suite after the save hook.
  - Requirements: 4, 8, 9, 11, 17.

## P1 — Streamlit product UI

- [x] 5. Build status, why, evidence, money, and action components
  - [ ] 5.1 Implement small renderers under `app/components/`: `status_hero.py`,
    `why_panel.py`, `evidence.py`, `money.py`, `actions.py`, `statement.py`.
  - [ ] 5.2 Include icon+text+color status, aria-live, Pip states, proof badges, meter,
    exact shortfalls, negated/ruled-out labels, due dates, and per-persona checked state.
  - [ ] 5.3 Run helper + integration tests.
  - Requirements: 2, 3, 4, 5, 7, 8, 11, 15, 17.

- [x] 6. Build what-if, packet, and red-team components
  - [ ] 6.1 Implement `what_if.py` using `CoachBackend` / real wallet rules on a copy; never
    mutate status; balloons only when motion is allowed.
  - [ ] 6.2 Implement `packet.py` download button and `redteam.py` proof display for SYN-0005.
  - [ ] 6.3 Add focused tests for what-if status preservation and injection escaping.
  - Requirements: 6, 9, 10, 17.

- [x] 7. Assemble the single-page Streamlit app
  - [ ] 7.1 Implement `app/main.py`: five persona buttons, guided Maria → James → Dev →
    red-team tour, settings, cached `MemberView`, responsive center + right agent panel.
  - [ ] 7.2 Default to system theme; light/dark override; large text, comfortable spacing,
    reduce motion; 360px stacking; exact disclaimer on every screen.
  - [ ] 7.3 Install pinned UI extra (`pip install -e ".[ui]"`) and smoke-start Streamlit.
  - Requirements: 1–17.

- [x] 8. Document run and extension points
  - [ ] 8.1 Update `app/README.md` with install/run/offline/live instructions, architecture,
    how to add a `ChatBackend` or coach tool, security boundaries, and known limits.
  - [ ] 8.2 Update `context.md` with final file map, commands, outcomes, and unresolved items.
  - Requirements: 13, 16, 17.

## P1 — Validation and demo rehearsal

- [ ] 9. Validate code and all five stories
  - [ ] 9.1 Run integration tests, contract checks, ownership check, ruff, and secret scan.
  - [ ] 9.2 Start Streamlit, then use Playwright MCP to open every persona; toggle themes and
    accessibility settings; run Dev's +$60 what-if; red-team SYN-0005 coach; confirm status is
    unchanged; check 360px viewport.
  - [ ] 9.3 Save `.kiro/specs/final-ui/ui-test-report.md` with pass/fail evidence and known gaps.
  - [ ] 9.4 Mark completed tasks and verify the original acceptance criteria one by one.

## Stretch — only after P0/P1 are green

- [ ] 10. Add text/CSV in-memory upload controls (PDF remains disabled).
- [ ] 11. Add experimental voice input; document that `components.html` cannot reliably return
  a transcript to Python.
- [ ] 12. Additional visual polish/animations (must obey reduce-motion).
