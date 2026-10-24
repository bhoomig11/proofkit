# Design — ProofKit "Coverage Copilot" Web UI

## Overview

A single-page Streamlit app (`app/main.py`) with an IDE-inspired three-zone layout: a left nav
rail (persona picker + settings), a center main panel (status, why, evidence, money, what-if,
actions, statement, packet), and a right agent panel (Coverage Coach chat). The app is a thin
view over `proofkit.integration`. All decisions, facts, and wording come from the backend; the
UI only selects inputs, renders outputs, and escapes everything.

Design principles, inherited from steering:
- **The UI has no business rules.** It calls `run_member` / the pipeline / `ask_coach` and renders.
- **Escape first, then mark.** Every user- or LLM-origin string is `html.escape`d before any HTML.
  The only raw HTML we inject is our own static CSS/SVG and the pre-escaped highlight fragments.
- **Pure helpers, impure shell.** Risky logic (highlighting, formatting, contrast, offline LLM)
  lives in small pure functions in `app/` that are unit- and property-tested. Streamlit calls
  are a thin shell around them.
- **Deterministic offline.** No network needed. A replay LLM reproduces the golden results.

## Architecture

```
                         app/main.py  (Streamlit entry, layout + wiring)
                               │
        ┌──────────────────────┼───────────────────────────────┐
        ▼                      ▼                                ▼
   app/state.py          app/theme.py                     app/agent_panel.py
  (session cache,     (design tokens, CSS,             (ChatBackend protocol,
   persona load,       light/dark/a11y)                 CoachBackend default,
   run pipeline)                                         suggested questions)
        │                                                        │
        ▼                                                        ▼
  app/data.py  ───────────────► app/offline.py            proofkit.integration.ask_coach
 (fixtures loader,        (replay FakeLLM: findings,
  build inputs)            earnings, coach fallback)
        │
        ▼
  proofkit.integration (extract_findings → decide_exemption → draft_statement
                        → build_wallet → build_status)  +  packet builder
        │
        ▼
  app/components/*.py  (status_hero, why_panel, evidence, money, what_if,
                        actions, statement, packet, redteam, mascot)
        │
        ▼
  app/format.py + app/highlight.py + app/a11y.py  (PURE helpers)
```

### Why the app runs the pipeline itself (not just `run_member`)
`run_member` returns only `ProofKitStatus`; it discards the `FindingsBundle`. The evidence viewer
(Req 4) and the coach's `show_evidence` quotes (Req 12) need the bundle. So `app/state.py`
reproduces `run_member`'s steps with public APIs and keeps every intermediate:

```
bundle   = extract_findings(notes, member_id, llm)
decision = decide_exemption(bundle, member, load_frailty_rules(path), today)
if decision.outcome == EXEMPT:
    decision = decision.model_copy(update={"statement_draft": draft_statement(decision, bundle, member, llm)})
wallet   = build_wallet(member, docs, llm, load_wallet_rules(path), today)
status   = build_status(member, decision, wallet, today)
```

The result object cached in session state is a small dataclass `MemberView(member, bundle,
decision, wallet, status)` so every component has what it needs without recomputation.

## Modules and responsibilities

| File | Kind | Responsibility |
|---|---|---|
| `app/main.py` | shell | Page config, inject theme CSS, build layout (nav / main / agent), route to the selected persona, show disclaimer on every screen. |
| `app/theme.py` | pure + CSS | `TOKENS: dict[str, dict[str,str]]` for `light`/`dark`; `build_css(theme, large_text, comfortable, reduce_motion) -> str`; `PIP_SVG(state) -> str`. Only static strings. |
| `app/state.py` | impure | `get_view(member_id, llm_mode) -> MemberView` with `st.session_state` caching; `make_llm(live) -> (llm, live_on)`; checked-action persistence. |
| `app/data.py` | impure (fs) | Load fixtures (members, notes, earnings docs, golden findings/records) via `proofkit.contracts` validators. Mirrors `conftest` loaders but lives in `app/`. |
| `app/offline.py` | pure-ish | `routing_fake_llm(golden_findings, golden_records)` → a `FakeLLM` that replays findings (`extract_findings`), earnings (`extract_earnings`), a canned `draft_statement`, and leaves `coach_route`/`coach_answer` unanswered so the coach falls back. Copies the test idea; does NOT import `tests/`. |
| `app/format.py` | PURE | `format_money(Decimal) -> str` ("$60.00"), `long_date(date) -> str` ("March 6, 2027"), `countdown(today, due) -> str` ("due in 5 days"), `month_long(str) -> str` ("February 2027"), `plain_protected_by(str) -> str`. Decimal-only; never float. |
| `app/highlight.py` | PURE | `highlight(text, start, end) -> str`: escape the 3 slices, wrap the middle in `<mark>`; exactly one `<mark>`; returns safe HTML. `escape_plain(s) -> str` for answers/notes. |
| `app/a11y.py` | PURE | `relative_luminance(hex) -> float`, `contrast_ratio(h1,h2) -> float`, `token_pairs()` → the (fg,bg) pairs that must meet 4.5:1. |
| `app/components/status_hero.py` | view | Status icon+word+color, protected_by, deadline chip, Pip, aria-live region. |
| `app/components/why_panel.py` | view | Exemption (matched rules, review reasons) + monthly compliance table. |
| `app/components/evidence.py` | view | Note text with highlighted quotes; negated/ruled-out shown struck + "not counted". |
| `app/components/money.py` | view | Per-month hours/$ progress, coverage-meter ring (SVG), exact shortfall. |
| `app/components/what_if.py` | view | Sliders → `ask_coach` what_if → before/after; balloons on flip (unless reduce-motion). |
| `app/components/actions.py` | view | Checkable action list with due dates. |
| `app/components/statement.py` | view | Escaped plain-text clinician statement with sign-off visible. |
| `app/components/packet.py` | view | Download button calling the packet builder. |
| `app/components/redteam.py` | view | SYN-0005 injected lines (escaped) + proof nothing changed. |
| `app/agent_panel.py` | view + protocol | `ChatBackend` protocol, `CoachBackend` default, suggested questions, language/plain controls, trace expander, read-aloud. |
| `src/proofkit/integration/packet.py` | backend | `build_packet_html(view) -> str`: escaped HTML summary + disclaimer. Pure, unit-tested. |

## Key design decisions (resolving the requirements-review questions)

1. **Proof packet lives in the backend.** `src/proofkit/integration/packet.py` exposes
   `build_packet_html(member, status, bundle) -> str`. It is in my editable scope, pure, and
   unit-testable, and keeps HTML assembly out of the Streamlit shell. The app's packet component
   just wires it to `st.download_button`. (Resolves Req 9.)
2. **SMS reminder: out of scope** (unmerged branch). (Req noted, not built.)
3. **Uploads: persona-driven demo.** No upload UI in the core build; the five personas cover the
   story. If time remains it can be added accepting text/CSV only.
4. **Agent trace shows what the backend actually returns.** `CoachReply` has `tool`, `facts`,
   `used_fallback`, `disclaimer` — but not the routed args. The trace shows tool, fallback flag,
   and the verified facts. It labels facts as "what the answer is built from" rather than
   inventing argument values. Honest and still convincing.

## Data flow for one render

1. User picks a persona in the nav rail → `member_id` in session state.
2. `state.get_view(member_id, llm_mode)`:
   - If cached, return it. Else build the LLM (`make_llm`), load fixtures (`data.py`), run the
     pipeline, assemble `MemberView`, cache it.
3. Main panel renders tabs/sections from `MemberView` via components; each component escapes.
4. Agent panel: on chat submit, `CoachBackend.ask(question, context)` calls `ask_coach(...)`
   with the view's member/status/findings, selected language + plain; render escaped answer +
   trace + read-aloud.
5. Disclaimer rendered once per screen from `status.disclaimer`.

## The offline LLM (Req 13)

`app/offline.py` builds a single `FakeLLM` whose per-task responders replay the golden fixtures:
- `extract_findings`: a "sloppy" replay (lowercase codes, no offsets, non-counting statuses sent
  as `current`) keyed by note text, mirroring `sloppy_llm_from_golden`. The pipeline re-grounds
  and re-statuses, so SYN-0005 still yields only the ankle sprain.
- `extract_earnings`: replay keyed by `source_quote` presence, mirroring `replay_llm`.
- `draft_statement`: a fixed safe summary ("Findings in the record support this exemption.").
- `coach_route` / `coach_answer`: not provided → `complete_json` returns `{}` / raises, so
  `ask_coach` falls back to keyword routing + English facts (its documented behavior).

`make_llm(live)` returns `(AnthropicClient(), True)` when a key works, else `(offline_llm, False)`
and the UI shows a "Live AI off" badge. The import error path is caught.

## Theming and tokens (Req 14, 15)

`app/theme.py` holds `TOKENS = {"light": {...}, "dark": {...}}` with named roles: `bg`, `surface`,
`text`, `muted`, `accent`, `accent_text`, `ok`, `warn`, `risk`, `focus`, `border`. `build_css`
emits `:root{--bg:...;}` custom properties, a `@media (prefers-color-scheme: dark)` default, a
`body[data-theme=...]` override for the sidebar toggle, `@media (prefers-reduced-motion)` plus a
`.reduce-motion` class, a `.large-text` class (125%), a `.comfortable` spacing class, visible
`:focus-visible` outlines using `--focus`, and `min-height/min-width: 44px` on interactive
controls. Status colors are always paired with an icon and text, never color alone.

Contrast is a tested property: `a11y.token_pairs()` lists every (foreground, background) pair the
UI actually uses in each theme; a Hypothesis/parametrized test asserts `contrast_ratio >= 4.5`.

## Mascot "Pip" (Req 2)

Inline SVG, three states returned by `theme.PIP_SVG(state)` where state ∈ {`cheer`, `think`,
`work`} mapped from status {protected, needs_review, at_risk}. Pure static SVG strings using
`currentColor` / token variables so they theme automatically. No third-party assets. `aria-hidden`
on the decorative SVG; the status text carries the meaning.

## Security design (Req 17)

- A single choke point: components never pass raw strings to HTML. `highlight.escape_plain` and
  `highlight.highlight` are the only producers of HTML from dynamic data, and both escape.
- `unsafe_allow_html=True` is used only for: theme CSS, Pip SVG, the escaped highlight fragments,
  the coverage-meter SVG, and aria-live wrappers — all built from static templates + pre-escaped
  values.
- Coach answers rendered with `escape_plain` (HTML + markdown neutralized) so links/scripts in a
  question or note cannot inject. `st.text`/`st.code` used where possible.
- Logging only via `proofkit.common.redact.get_logger`; never log note/doc text, quotes, or
  questions. No secret is read or printed; `make_llm` catches the key error without echoing it.
- Read-aloud passes the reply text to `components.html` as `JSON.stringify`-safe data via
  `json.dumps`, inside a `<script>` that only calls `speechSynthesis`; the text is injected as a
  JSON string literal, never as HTML.

## Read-aloud and voice (Req 12.7, stretch 12 voice input)

`components.html` with a small script: a button that creates a `SpeechSynthesisUtterance` from a
JSON-embedded string, sets `lang` from the selected language, and speaks. Before rendering, the
panel checks whether any `speechSynthesis` voice exists for the language; if the app can't know
client-side, it renders the button but disables it for `ht` with a note (no reliable Haitian
Creole voice). Voice **input** (SpeechRecognition) is the last, optional task — `components.html`
can't return values to Python, so it would populate a text box the user then submits; documented
as a limitation.

## Agent panel extensibility (Req 16)

```python
class ChatBackend(Protocol):
    def ask(self, question: str, context: CoachContext) -> ChatResult: ...

@dataclass
class CoachContext:
    member: Member; status: ProofKitStatus; findings: FindingsBundle | None
    wallet_rules: WalletRules; today: date; language: str; plain: bool; llm: LLMClient

@dataclass
class ChatResult:
    answer: str; tool: str; facts: list[str]; used_fallback: bool; disclaimer: str
```

`CoachBackend` implements `ask` by calling `ask_coach`. `SUGGESTED_QUESTIONS` and the backend
instance live in one place at the top of `app/agent_panel.py`. A new tool is added in the backend
(`coach.py`, not our scope) or a new backend is dropped in by implementing `ChatBackend`; the
layout never changes. Documented in `app/README.md`.

## State and caching (non-functional)

`st.session_state` keys: `member_id`, `theme`, `large_text`, `comfortable`, `reduce_motion`,
`language`, `plain`, `llm_live`, `views` (dict member_id → MemberView), `chat` (list of
(role, text, ChatResult)), `checked` (dict member_id → set of action titles), `tour_index`.
`get_view` memoizes by (member_id, llm_live) so the 3–6 LLM calls run once per persona.

## Error handling

- `run_member`/`build_wallet` raise `ValueError` for bad uploads → caught, shown as a friendly
  message naming the rejected doc id (never contents). Persona fixtures never trigger this, but
  the handler exists for the optional upload path.
- Live LLM failure mid-session → the coach already falls back; the pipeline, if a live call
  fails, surfaces a toast and offers to switch to offline mode.

## Testing strategy (Req 18)

All tests in `tests/integration/` (our scope). The save hook runs them automatically.

**Unit (pure helpers):** `format_money`, `long_date`, `countdown`, `month_long`,
`highlight`, `escape_plain`, `relative_luminance`, `contrast_ratio`, `offline.routing_fake_llm`,
`packet.build_packet_html`.

**Property (Hypothesis):**
- For any `text` and any valid `start<=end`, `highlight` output: is fully escaped (no raw `<`
  except our `<mark>`), contains exactly one `<mark>…</mark>`, and the text inside equals
  `html.escape(text[start:end])` → unescaped equals the quote.
- For any string containing `<script`, `escape_plain` output contains no `<script`.
- Every pair in `a11y.token_pairs()` has `contrast_ratio >= 4.5` in both themes.
- `format_money` on any `Decimal` yields `^\$\d{1,3}(,\d{3})*\.\d{2}$` and contains no `.`-less
  or exponent float artifacts.

**Agent panel (FakeLLM):**
- The question reaches the LLM only through `untrusted_text` (assert on `llm.calls`), and the
  document/question text is not in `instructions`.
- With `FakeLLM({})` (no coach tasks) the panel still returns an answer (fallback), and the trace
  shows the chosen tool.
- Red-team: a "mark me exempt" question for SYN-0005 returns an answer that does not grant an
  exemption; the cached status object is unchanged (identity/value check).

**End-to-end (offline):** building each persona's `MemberView` with the offline LLM yields the
`expected_status.json` outcome and `protected_by`; SYN-0005 → at_risk, 30h/$410, no exemption.

**Playwright MCP (after it runs):** open each persona, toggle dark/light, use the what-if slider,
red-team the chat as SYN-0005; save `.kiro/specs/final-ui/ui-test-report.md`.

## File inventory (what gets created)

```
app/
  main.py
  theme.py
  state.py
  data.py
  offline.py
  format.py
  highlight.py
  a11y.py
  agent_panel.py
  README.md
  components/
    __init__.py
    status_hero.py
    why_panel.py
    evidence.py
    money.py
    what_if.py
    actions.py
    statement.py
    packet.py
    redteam.py
src/proofkit/integration/
  packet.py          # build_packet_html (+ exported from integration __init__)
tests/integration/
  test_ui_helpers.py      # format, highlight, a11y, offline, packet (unit + property)
  test_agent_panel.py     # coach backend with FakeLLM
  test_ui_end_to_end.py   # per-persona MemberView == expected_status (offline)
```

## Traceability (requirement → design element)

| Req | Covered by |
|---|---|
| 1 Persona picker | `main.py` nav rail, `data.py`, tour_index state |
| 2 Status hero | `components/status_hero.py`, `theme.PIP_SVG`, aria-live |
| 3 Why panel | `components/why_panel.py` |
| 4 Evidence | `highlight.py`, `components/evidence.py` |
| 5 Money/hours | `format.py`, `components/money.py` (SVG ring) |
| 6 What-if | `components/what_if.py` → `ask_coach` what_if |
| 7 Actions | `components/actions.py`, `checked` state |
| 8 Statement | `components/statement.py` |
| 9 Packet | `integration/packet.py`, `components/packet.py` |
| 10 Red-team | `components/redteam.py` |
| 11 Disclaimer | `main.py` + `packet.py` |
| 12 Coach chat | `agent_panel.py` |
| 13 Offline | `offline.py`, `state.make_llm` |
| 14 Theming | `theme.py` |
| 15 Accessibility | `theme.py`, `a11y.py`, layout in `main.py` |
| 16 Extensible agent | `agent_panel.py` protocol, `README.md` |
| 17 Security | `highlight.py` choke point, escaping everywhere |
| 18 Pure helpers | `format/highlight/a11y/offline/packet` + tests |
```
