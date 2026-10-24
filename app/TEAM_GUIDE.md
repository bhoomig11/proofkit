# Team guide: building on the Coverage Copilot UI

For teammates adding features to the UI or the Coverage Coach. 5-minute read.

## 1. Get it running (2 minutes)
```bash
git switch main && git pull
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -e ".[dev,ui]"
streamlit run app/main.py                               # http://localhost:8501, works offline, no API key
pytest tests/integration -q                             # should be all green
```
Live AI for the coach (optional): put `ANTHROPIC_API_KEY=...` in `.env` (never commit it) and flip "Live AI for the
coach" in the sidebar.

## 2. How it fits together
```
fixtures/ (synthetic personas)
   └─ app/data.py          load + validate members, notes, earnings docs
       └─ app/state.py     build_member_view(): extraction → decide_exemption → statement → wallet → build_status
           │               (offline: app/offline.py replays golden LLM answers, so it's deterministic and free)
           └─ app/main.py  the page: sidebar · header · 6 tabs · coach panel
                 ├─ app/whatif.py        what-if sliders (real wallet rules on a COPY)
                 ├─ app/agent_panel.py   Coverage Coach chat (ChatBackend → proofkit.integration.ask_coach)
                 ├─ proofkit.integration.build_packet_html   proof packet download
                 └─ app/theme.py, a11y.py, format.py, highlight.py   look, contrast, safe text
```
`MemberView` (in `state.py`) is everything one persona needs: `member`, `findings`, `exemption`, `wallet`, `status`.

## 3. Where to add things
| I want to… | Do this |
|---|---|
| Add a tab or panel | In `app/main.py`, add a label to `st.tabs([...])` and a `with tabs[i]:` block. Read from `view` / `status`. |
| Add a coach skill | In `src/proofkit/integration/coach.py`: add the tool name to `Tool`, an args model in `ARGS_MODEL`, a fact function, a line in `ROUTE_INSTRUCTIONS`, and a keyword fallback. Test in `tests/integration/test_coach.py`. |
| Swap or extend the agent | Write a class with `ask(question, context) -> ChatResult` (see `ChatBackend` in `agent_panel.py`) and pass `render_agent_panel(..., backend=MyBackend())`. |
| Change colors or the theme | Edit `TOKENS` in `app/theme.py`. The tests check every text/background pair for WCAG 4.5:1 contrast in both themes. |
| Add a persona | Add the member, notes and docs to `fixtures/` (P1A/P2 own those folders) plus `expected_status.json`; it appears in the sidebar automatically. |
| Add a suggested question | `SUGGESTED_QUESTIONS` in `app/agent_panel.py`. |
| Change the packet | `src/proofkit/integration/packet.py`. Escape every dynamic value with `_e()`. |

## 4. Rules that keep us safe (tests enforce most of them)
- **Never render user or document text as HTML.** Use `st.text(...)`, or `escape_plain()` before any
  `unsafe_allow_html=True`. Only our own static CSS/SVG goes in unescaped.
- **The LLM never decides.** Status comes from `build_status` and the module rules. The coach is read-only, and the
  what-if works on a copy.
- **The disclaimer stays on every screen:** "ProofKit organizes evidence. MassHealth makes all eligibility determinations."
- **Synthetic data only** (`SYN-####`). No real names, notes or pay stubs, and no third-party logos (video rule).
- **Accessibility:** icon + text + color (never color alone), labels on every control, and motion only when
  "Reduce motion" is off.
- **Ownership:** UI work goes on a `final/<name>` branch. It may edit `app/`, `src/proofkit/integration/`,
  `tests/integration/` and `.kiro/specs/`. Don't edit contracts, common or other modules.

## 5. Workflow
```bash
git switch main && git pull && git switch -c final/<your-feature>
# write a failing test in tests/integration/ → implement → green
pytest tests/integration -q && make check-contracts check-ownership && ruff check app src tests
git push -u origin final/<your-feature>          # then open a PR into main
```
Using Kiro? The spec and progress log are in `.kiro/specs/final-ui/` (`requirements.md`, `design.md`, `tasks.md`,
`context.md`). Add your own spec under `.kiro/specs/<feature>/`, and note which Kiro features you used for the write-up.

## 6. Tests you'll touch
| File | Covers |
|---|---|
| `tests/integration/test_ui_app.py` | Headless `AppTest`: every persona renders, themes, red team, offline coach |
| `tests/integration/test_ui_whatif.py` | What-if flips Dev to Protected without changing his real status |
| `tests/integration/test_ui_helpers.py` | Money/dates, escaping, highlighting (property tests), contrast, packet |
| `tests/integration/test_agent_panel.py` | Coach adapter: untrusted input, no-key fallback, injection can't change status |
| `tests/integration/test_ui_end_to_end.py` | All 5 personas build offline to the expected status |

## 7. Open ideas (pick one, tell the team)
- Playwright browser test via the Kiro MCP server, with a report in `.kiro/specs/final-ui/ui-test-report.md`
- Text/CSV upload (in memory, size-capped; PDF stays off until P2 re-enables it)
- 🎤 Voice input (stretch: `components.html` can't return the transcript to Python, so it needs a custom component)
- SMS reminder preview (≤ 160 characters, first name only)
- Polish: a demo-tour narration, better mobile layout, Pip animations (respecting reduce motion)

Demo flow for the video (under 3 minutes): Maria (exempt, lupus highlighted) → James (negation struck through,
protected by hours) → Dev (at risk; drag the what-if to +$60 → Protected 🎈) → SYN-0005 Red team tab → ask the coach a question.
