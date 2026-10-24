# ProofKit

**Helping MassHealth members keep their coverage when the federal work requirements start on Jan 1, 2027.**

The state is building tools for the agency. ProofKit is a tool for the *member* (and their clinic). It builds a proof packet that shows either:
1. **an exemption**, such as medical frailty, found in their clinical notes with a quote supporting each finding, or
2. **compliance**: 80+ hours a month, or income of at least $580 a month, assembled from scattered gig-work earnings statements.

## Start here (read in this order)
| # | File | Why |
|---|------|-----|
| 1 | `CLAUDE.md` | Rules every Claude Code session follows. **Non-negotiable.** |
| 2 | `docs/00_CONTEXT.md` | The problem, the research, the numbers for the pitch |
| 3 | `docs/01_ARCHITECTURE.md` | The modules, who owns what, and the data flow |
| 4 | `docs/02_CONTRACTS.md` | The JSON formats passed between modules. **Frozen.** |
| 5 | `docs/roles/<YOUR_ROLE>.md` | Your scope, boundaries, and checklist |
| 6 | `docs/03_TDD_WORKFLOW.md` | How Claude Code must work (red → green → refactor) |
| 7 | `docs/04_SECURITY.md` | Security rules |
| 8 | `docs/05_INTEGRATION.md` | How the modules come together without surprises |
| 9 | `docs/06_TIMELINE.md` | The hour-by-hour plan |

## Team
| Role | Person | Owns |
|------|--------|------|
| P1A: Note Understanding | @arshmehar | `src/proofkit/extraction/` |
| P1B: Exemption Reasoning + Eval | @bhoomig | `src/proofkit/reasoning/`, `eval/` |
| P2: Gig-Hours Wallet | ___ | `src/proofkit/wallet/` |
| FINAL: Integration + UI (everyone, last 4–5h) | all | `src/proofkit/integration/`, `app/` |

## Setup (5 minutes)
**Get the `setup/` folder from the team (shared chat/drive, NOT git)** and put it at the repo root. It holds the Claude Code config (`CLAUDE.md`, `.claude/`, module rules) and is gitignored.
```bash
bash setup/install.sh         # links CLAUDE.md, .claude/ and module CLAUDE.md files from setup/ (--copy on Windows)
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+
pip install -e ".[dev]"
cp .env.example .env          # add your ANTHROPIC_API_KEY locally. NEVER commit it.
pre-commit install
make check-contracts          # must be green before anyone writes code
```

## Each person works in their own git worktree
```bash
git worktree add ../pk-p1a -b p1a/main    # P1A
git worktree add ../pk-p1b -b p1b/main    # P1B
git worktree add ../pk-p2  -b p2/main     # P2
bash setup/install.sh ../pk-<you>         # Claude config into your worktree (links back to this setup/)
cd ../pk-<you> && claude                  # start Claude Code there
```
Then paste the **kickoff prompt** from the bottom of your role doc into Claude Code.

## Commands
```
make test-p1a | test-p1b | test-p2    # your module's tests
make check-contracts                  # contract tests + contract lock
make check-ownership                  # did this branch touch only its own paths?
make security                         # secret scan + bandit + pip-audit (if installed)
make check                            # everything (the gate before merging)
make eval                             # accuracy numbers for the pitch
```

All data in this repo is **synthetic**. No real PHI or PII, ever. See `docs/04_SECURITY.md`.
