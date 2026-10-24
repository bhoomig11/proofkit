# app/: Coverage Copilot (Streamlit UI)

## Run it (works offline, no API key needed)
```bash
python3 -m venv .venv && source .venv/bin/activate      # Python 3.11+
pip install -e ".[dev,ui]"
streamlit run app/main.py                                # opens http://localhost:8501
```
- **Offline (default):** the evidence pipeline replays the synthetic golden results, and the Coverage Coach answers
  from verified facts with keyword routing. No key, no cost, deterministic, so it's safe for judges.
- **Live AI:** put `ANTHROPIC_API_KEY=...` in `.env` (never commit it) and switch on "Live AI for the coach" in the
  sidebar. The coach then routes and words answers with Claude; every fact still comes from tested code.

## What's on screen
| Area | What it shows |
|---|---|
| Sidebar | 5 synthetic personas, 🎬 demo tour (Maria → James → Dev → red team), theme (system/light/dark), larger text, more spacing, reduce motion, Live AI switch |
| Header | Pip the mascot + status (icon + text + color), deadline countdown, what protects the member |
| ✅ Next steps | Action checklist with due dates |
| 💡 Why | Exemption decision (rules, review reasons) and the 80 h / $580 check per month |
| 📄 Evidence | Clinical notes: counted quotes highlighted, denied/ruled-out/family/past struck through; clinician statement |
| ⏱️ Hours & money | Progress toward 80 h and $580, proof badges, 🔮 what-if sliders (real rules on a copy) |
| 📦 Proof packet | Escaped HTML download (`proofkit.integration.build_packet_html`) |
| 🛡️ Red team | Injected instructions found in notes/pay stubs, shown as ignored, with the unchanged result |
| Right panel | Coverage Coach chat: EN/ES/PT/HT, plain language, suggested questions, agent trace, read-aloud |

## Code map
`main.py` (layout) · `state.py` (pipeline per member) · `data.py` (fixtures) · `offline.py` (replay LLM) ·
`whatif.py` (hypothetical status) · `agent_panel.py` (chat) · `theme.py` / `a11y.py` (tokens, WCAG contrast, Pip) ·
`format.py` / `highlight.py` (safe text).

## Extend the agent
The chat talks to a `ChatBackend` (`agent_panel.py`): `ask(question, context) -> ChatResult`. `CoachBackend` wraps
`proofkit.integration.ask_coach`. To add a capability, add a read-only tool in `src/proofkit/integration/coach.py`
(name + args model + fact function + a test), or pass your own backend: `render_agent_panel(..., backend=MyBackend())`.

## Safety rules (tested)
Every dynamic string is rendered as plain text or passed through `html.escape` before HTML; only our static CSS/SVG is
injected. The coach is read-only and never changes a status. Disclaimer on every screen. Synthetic data only.

Tests: `pytest tests/integration` (helpers, offline pipeline, coach adapter, packet, what-if, and a headless
`AppTest` smoke test of every persona).
