# RenewRight

**A member-side proof packet so eligible MassHealth members keep their coverage under the 2027 work requirements.**

[About RenewRight](https://drive.google.com/file/d/1igf1xTW2h6-qQfa0UmlPYb26g1EmDsta/view?usp=drive_link)

Track: **Healthcare & Biotech**. The Python package, contracts and some UI strings still use the working name ProofKit (`proofkit`).

## Why it matters
Source: `docs/00_CONTEXT.md` (which lists the original sources: mass.gov, Boston Globe, Healey administration, MHA summary of the BCBSMA Foundation report).

- From **January 1, 2027**, MassHealth ACA-expansion adults aged 19–64 must show 80 hours a month of work, school or community service, or income of at least $580 a month ($7.25 × 80), or qualify for an exemption. Many must also renew every 6 months.
- About **360,000** members may face the new reporting requirements.
- MassHealth estimates about **175,000** could lose coverage. A Blue Cross Blue Shield of Massachusetts Foundation report puts losses at **141,000–203,000**.
- Most people who lose coverage are eligible. They lose it over **paperwork**.

The state's tools serve the agency. We couldn't find a member-side tool in Massachusetts, so we built one for the person and their clinic.

## Live demo
Live demo: <link coming from Bhoomika>

## Run it offline (Python 3.11+)
No API key needed. All personas are synthetic (`fixtures/`, SYN-0001..0005).
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev,ui]"
streamlit run app/main.py            # http://localhost:8501, offline replay of synthetic personas
pytest -q                            # non-live suite; live LLM tests are opt-in (pytest -m live)
```

## What it does
- **Exemption from clinical notes:** finds medical-frailty conditions in synthetic notes, each backed by an exact quote and offsets, highlighted in the note. Negations like "denies depression" or "r/o CHF" don't count. Rules code decides, then a clinician statement is drafted for review.
- **80 h / $580 wallet:** turns gig earnings statements (CSV, text, PDF) into a month-by-month pass/fail with an audit trail back to each source quote.
- **Status and deadlines:** PROTECTED / NEEDS_REVIEW / AT_RISK per member, the shortfall in plain words ("$60 short in Feb 2027") and the proof due date, plus a what-if slider.
- **Escaped HTML proof packet:** downloadable from the app; every dynamic value is HTML-escaped (`src/proofkit/integration/packet.py`, plus the Kiro-built `proof_packet.py`).
- **Coverage Coach and offline demo mode:** a read-only coach that answers from verified facts, with a keyword fallback when there's no key. The app replays golden fixtures offline (`app/offline.py`, `proofkit.integration.demo`).

- **SMS reminders in English, Spanish and Portuguese:** `proofkit.integration.reminder.sms_reminder(member, status, lang="en"|"es"|"pt")`. Each message is at most 160 printable-ASCII characters (Spanish and Portuguese are written ASCII-safe, since accented letters would force UCS-2 and a 70-character SMS) and uses the first name only. Not wired into the app yet.
- **RenewRight MCP server:** `python -m proofkit.integration.mcp_server` speaks MCP (JSON-RPC 2.0 over stdio, standard library only) with five read-only tools over the synthetic fixtures, computed offline: `list_members`, `member_status`, `wallet_months`, `sms_reminder` and `triage`. It is registered for Kiro in `.kiro/settings/mcp.json`, with a read-only `navigator` agent in `.kiro/agents/navigator.json`.

## How we used Kiro
The core modules (extraction, reasoning, wallet) were built first with Claude Code. Kiro came in for the FINAL phase: IDE spec mode built the proof packet, and headless Kiro CLI jobs with least-privilege agents did test-first work on the SMS reminder, PDF uploads, offline demo mode and the fictional-brand rename.
`.kiro/` holds the steering, hooks, agents and specs. Hypothesis property tests from Kiro specs found 2 real bugs in merged wallet code. Kiro never committed or pushed.
Details and commit evidence: [KIRO_WRITEUP.md](KIRO_WRITEUP.md).

## Safety
- **Synthetic data only.** Every member is `SYN-####`. No real PHI or PII. See `docs/04_SECURITY.md`.
- **The LLM never decides.** It extracts; tested rules code (`decide_exemption`, `evaluate_months`, `compute_deadlines`, `build_status`) decides. Every quote is grounded in its source, and injected instructions are dropped (SYN-0005 stays AT_RISK).
- **Disclaimer:** "RenewRight organizes evidence. MassHealth makes all eligibility determinations." The app currently shows this with the working name ("ProofKit organizes evidence. ...", `app/main.py`).

---

## Start here (read in this order)
| # | File | Why |
|---|------|-----|
| 1 | `CLAUDE.md` / `.kiro/steering/` | Rules every Claude Code and Kiro session follows. **Non-negotiable.** |
| 2 | `docs/00_CONTEXT.md` | The problem, the research, the numbers for the pitch |
| 3 | `docs/01_ARCHITECTURE.md` | The modules, who owns what, and the data flow |
| 4 | `docs/02_CONTRACTS.md` | The JSON formats passed between modules. **Frozen.** |
| 5 | `docs/roles/<YOUR_ROLE>.md` | Your scope, boundaries, and checklist |
| 6 | `docs/03_TDD_WORKFLOW.md` | How the coding agents must work (red → green → refactor) |
| 7 | `docs/04_SECURITY.md` | Security rules |
| 8 | `docs/05_INTEGRATION.md` | How the modules come together without surprises |
| 9 | `docs/06_TIMELINE.md` | The hour-by-hour plan |
| 10 | `app/TEAM_GUIDE.md` | Building on the Streamlit UI and the Coverage Coach |

## Team
| Role | Person | Owns |
|------|--------|------|
| P1A: Note Understanding | @arshmehar | `src/proofkit/extraction/` |
| P1B: Exemption Reasoning + Eval | @bhoomig | `src/proofkit/reasoning/`, `eval/` |
| P2: Gig-Hours Wallet | Dhruv | `src/proofkit/wallet/` |
| FINAL: Integration + UI | all | `src/proofkit/integration/`, `app/` |

## Setup for contributors (5 minutes)
Claude Code config (`CLAUDE.md`, `.claude/`, module rules) lives in the `setup/` folder, shared by the team outside git, and is gitignored. Kiro config (`.kiro/steering`, `hooks`, `agents`, `settings`, `specs`) is in the repo.
```bash
bash setup/install.sh         # links CLAUDE.md, .claude/ and module CLAUDE.md files from setup/ (--copy on Windows)
python -m venv .venv && source .venv/bin/activate   # Python 3.11+ (Windows: py -3.11 -m venv .venv)
pip install -e ".[dev,ui]"
cp .env.example .env          # optional: add your ANTHROPIC_API_KEY locally for live AI. NEVER commit it.
pre-commit install
make check-contracts          # must be green before anyone writes code
```

## Each person works in their own git worktree
Branch prefixes are enforced by `make check-ownership`: `p1a/`, `p1b/`, `p2/`, `final/`.
```bash
git worktree add ../pk-p1a -b p1a/main    # P1A
git worktree add ../pk-p1b -b p1b/main    # P1B
git worktree add ../pk-p2  -b p2/main     # P2
git worktree add ../pk-final -b final/<name>   # integration / UI
bash setup/install.sh ../pk-<you>         # Claude config into your worktree (links back to this setup/)
cd ../pk-<you> && claude                  # or open it in Kiro
```
Then paste the **kickoff prompt** from the bottom of your role doc into your agent.

## Commands
On Windows, run make as `mingw32-make <target> PY=.venv/Scripts/python.exe`.
```
make test                             # whole non-live suite
make test-p1a | test-p1b | test-p2    # a module's unit + golden acceptance tests with coverage
make test-final                       # tests/integration
make check-contracts                  # contract tests + contract lock
make check-ownership                  # did this branch touch only its own paths?
make lint                             # ruff check src tests scripts
make security                         # secret scan + bandit + pip-audit (bandit/pip-audit failures are ignored)
make check                            # everything (the gate before merging)
make eval                             # accuracy numbers for the pitch
```

All data in this repo is **synthetic**. No real PHI or PII, ever. See `docs/04_SECURITY.md`.
