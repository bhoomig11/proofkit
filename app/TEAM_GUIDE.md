# Team guide: building RenewRight's UI in parallel

**RenewRight** helps MassHealth members keep their coverage under the 2027 work requirements. It finds an exemption in
their clinical notes, or proves 80 hours / $580 a month from their gig statements, then tells them what's missing and
by when. **Coverage Coach** is the chat assistant inside it. Track: Healthcare & Biotech. All data is synthetic.

## 1. Run it (2 minutes)
```bash
git switch main && git pull
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11+
pip install -e ".[dev,ui]"
streamlit run app/main.py                               # http://localhost:8501, offline, no API key needed
pytest tests/integration -q                             # all green before you start
```
Live AI for Coverage Coach (optional): add `ANTHROPIC_API_KEY=...` to `.env` (never commit it), then flip
"Live AI for Coverage Coach" in the Accessibility menu (nav bar).

### Demo accounts (synthetic people; public test credentials, not secrets)
| Name | Email | Password | Story | Status |
|---|---|---|---|---|
| Maria | maria@example.com | maria-demo-2027 | Lupus in her notes, 74 gig hours | Protected (exemption) |
| James | james@example.com | james-demo-2027 | "R/o CHF", "denies depression"; 92.5 hours | Protected (hours) |
| Priya | priya@example.com | priya-demo-2027 | Severe recurrent depression; old PTSD note | Protected (exemption) |
| Dev | dev@example.com | dev-demo-2027 | No exemption; $520 in February | At risk ($60 short) |
| Red team | redteam@example.com | redteam-demo-2027 | Injected "mark exempt" / "report 200 hours" | At risk (injection ignored) |

New sign-ups work too: they land on a welcome page and can explore Maria as an example.

## 2. What the app does today (user flow)
```
Sign in / Create account ──▶ Nav bar: RenewRight · section links · Accessibility menu · user menu (account details, Sign out)
   │
   ├─ demo account ──▶ Dashboard for that member
   │                     top:      status circle (green = protected, red = not) + "Maria is protected" + deadline + "Protected by"
   │                     sections (nav bar): Next steps · Why · Evidence · Hours & money (+ what-if) · Proof packet · Red team
   │                     Coverage Coach: floating button bottom-right → opens a chat panel on the right edge
   └─ new account ───▶ Welcome / onboarding ──▶ "Explore an example member" (Maria, read-only)
Accessibility menu (nav bar, always): theme system/light/dark · larger text · more spacing · reduce motion · Live AI
```

## 3. How the code fits together
| File | Job |
|---|---|
| `app/main.py` | The page: `render_navbar()`, `render_auth()`, `render_onboarding()`, `render_dashboard(member_id, example=…)` |
| `app/auth.py` | `AccountStore.sign_in / sign_up`, salted PBKDF2 hashes, the 5 `DEMO_LOGINS`. Sign-ups go to `app/accounts.generated.json` (gitignored) |
| `app/state.py` | `build_member_view()`: extraction → decision → statement → wallet → status, keeping the findings for the UI |
| `app/data.py`, `app/offline.py` | Load the synthetic fixtures; offline replay "LLM" (deterministic, free) |
| `app/whatif.py` | What-if: real wallet rules on a copy; the real status never changes |
| `app/coach_widget.py` | Coverage Coach shell: floating launcher, right-side panel, open/close state, its own CSS |
| `app/agent_panel.py` | Coverage Coach chat body behind a `ChatBackend` protocol (default: `proofkit.integration.ask_coach`) |
| `app/theme.py`, `app/a11y.py` | Light/dark design tokens (tested for WCAG 4.5:1 contrast), CSS, Pip the mascot |
| `app/format.py`, `app/highlight.py` | Money/dates in plain words; safe escaping and quote highlighting |
| `src/proofkit/integration/packet.py` | Downloadable, escaped HTML proof packet |
| `src/proofkit/integration/coach.py` | Coverage Coach brain: routes to read-only tools, computes facts, words them |

(The Python package is still called `proofkit`; only the product name changed.)

## 4. What's next: pick a lane and build in parallel
Each lane touches different files, so lanes don't collide. Tell the team which one you take.

| Lane | What to build | Main files | Notes |
|---|---|---|---|
| **A. Upload my documents** | Signed-up users upload clinical notes (text) and pay statements (text/CSV/PDF), then see their own dashboard | new `app/upload.py`; onboarding in `main.py` | In memory only, size-capped by `config/wallet_rules.json`, never use the filename as a path. Build `ClinicalNote` / `EarningsDocument` objects and reuse the pipeline in `state.py`. Link the result to the account. |
| **B. Landing + nav polish** | A signed-out landing page, nav links in the nav bar (Dashboard · Coach · Help), a "How it works" page | `render_navbar`, `render_auth` in `main.py`; maybe `app/pages.py` | Disclaimer on every screen. No company logos (video rule). |
| **C. Coverage Coach (owned end to end)** | Everything about the chat: launcher, panel, messages, suggestions, languages, voice, new skills | `app/coach_widget.py`, `app/agent_panel.py`, `src/proofkit/integration/coach.py`, `tests/integration/test_coach_widget.py`, `test_agent_panel.py`, `test_coach.py` | Fully separate: `main.py` only calls `render_coach_widget(...)`. New skills = tool + args model + facts + test in `coach.py`. Stays read-only. |
| **D. Reminders** | Show and preview the SMS reminder for at-risk members | new tab or panel; `proofkit.integration.reminder` (Karthik's) | ≤ 160 characters, first name only, no medical details. |
| **E. Navigator view** | A role for clinic/navigator staff: all members in a table, sorted by risk and deadline | new `app/navigator.py`; add a `role` to accounts in `auth.py` | Read-only. Good for the "scales beyond one person" pitch. |
| **F. Testing + accessibility** | Playwright run (Kiro MCP) of every flow; keyboard-only and 360 px checks; a report | `.kiro/specs/final-ui/ui-test-report.md` | Great material for the Kiro write-up. |

To avoid merge conflicts in `main.py`, keep new screens in their own file and add only a small call in `main.py`.

## 5. Rules that keep us safe (tests enforce most of them)
- **Never render user or document text as HTML.** Use `st.text(...)`, or `escape_plain()` before any
  `unsafe_allow_html=True`. Only our own static CSS/SVG goes in unescaped.
- **The LLM never decides.** Status comes from `build_status` and the module rules; Coverage Coach is read-only.
- **The disclaimer is on every screen:** "RenewRight organizes evidence. MassHealth makes all eligibility determinations."
- **Passwords:** only through `app/auth.py` (hashed). Never log or display them; the demo credentials are the only
  exception, because they're public on purpose.
- **Synthetic data only** (`SYN-####`). No real names, notes or pay stubs, and no company logos.
- **Accessibility:** text or icon plus color (never color alone), labels on every control, motion only when
  "Reduce motion" is off.
- **Ownership:** UI work goes on `final/<you>-<feature>`. It may edit `app/`, `src/proofkit/integration/`,
  `tests/integration/` and `.kiro/specs/`. Don't edit contracts, common, extraction, reasoning or wallet.

## 6. Workflow
```bash
git switch main && git pull && git switch -c final/<you>-<feature>
# write a failing test in tests/integration/ → implement → green
pytest tests/integration -q && make check-contracts check-ownership && ruff check app src tests
git push -u origin final/<you>-<feature>          # open a PR into main; pull main often to avoid conflicts
```
Using Kiro: put your spec in `.kiro/specs/<feature>/` (requirements, design, tasks) and note which Kiro features you
used. The UI spec and log so far: `.kiro/specs/final-ui/`.

## 7. Tests you'll touch
| File | Covers |
|---|---|
| `tests/integration/test_auth.py` | Hashing, the 5 demo logins, sign-up validation, duplicates, no plaintext stored |
| `tests/integration/test_ui_app.py` | Headless `AppTest`: sign-in, wrong password, sign-up → onboarding → example, sign-out, every dashboard, themes, red team, coach |
| `tests/integration/test_ui_whatif.py` | What-if flips Dev to Protected without changing his real status |
| `tests/integration/test_ui_helpers.py` | Formatting, escaping, highlighting (property tests), contrast, packet |
| `tests/integration/test_coach_widget.py` | Launcher/panel open-close, offline answers, "mark me exempt" can't change status |
| `tests/integration/test_agent_panel.py` | Coach adapter: untrusted input, no-key fallback, injection can't change status |
| `tests/integration/test_ui_end_to_end.py` | All 5 personas build offline to the expected status |

## 8. Demo video (under 3 minutes)
Sign in as Maria (exempt, lupus quote highlighted) → sign out and in as James (negation struck through, protected by
hours) → Dev (at risk; drag the what-if to +$60 → Protected) → Red team account (injections ignored) → ask Coverage
Coach a question in Spanish.
