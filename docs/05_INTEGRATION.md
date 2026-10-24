# 05: Integration plan (so the end doesn't hurt)

## Branches and worktrees
- `main` is always green on `make check-contracts`.
- Everyone works on their own long-lived branch (`p1a/main`, `p1b/main`, `p2/main`) in their **own git worktree**, so the three Claude Code sessions never share a working directory.
- Merge to `main` through a PR (or a local merge plus `make check`) at each checkpoint. Rebase on `main` first.

## Why there won't be merge conflicts
Each branch may only touch its own paths (`make check-ownership`). The shared files are frozen. With disjoint file sets, merges can't conflict.

## Build against fixtures, not against each other
| You need | Before your teammate merges, use | After they merge, switch to |
|---|---|---|
| P1B needs findings | `fixtures/findings/*.golden.json` | (keep the golden files for unit tests) the real `extract_findings` in integration only |
| FINAL needs decisions and wallets | the expected fixtures | the real modules via `run_member` |

## Checkpoints (merge to main)
| When | What must be green |
|---|---|
| **CP0** (hour 0:30) | Scaffold on main, `make check-contracts` green on all 3 laptops, worktrees created, API key works (one live call each) |
| **CP1** (about 35% of time) | Each module: at least half its spec tests green. Merge to main. Each person runs `make test` on main: other modules may be red, but nothing of yours may break. |
| **CP2** (about 65%) | All spec and acceptance tests green per module. Merge. Start FINAL: `tests/integration` |
| **CP3** (last 4–5h) | `make check` fully green on main. UI built. Feature freeze 1 hour before the end. |

## Contract change protocol (rare!)
1. Whoever needs it runs `/contract-question` in Claude Code and posts the proposal to the team chat.
2. All 3 humans agree **out loud**.
3. ONE person makes the change on a `contract/<name>` branch: edit the models, update fixtures if needed, run `make lock-contracts`, and update `docs/02_CONTRACTS.md`.
4. Merge to main. Everyone else rebases immediately.
5. Prefer **additive, optional fields**. Never rename or remove fields during the hackathon.

## FINAL phase (whole team, last 4–5 hours)
1. Implement `build_status` test-first: the status rules are in `integration/orchestrator.py`. Add unit tests in `tests/integration/test_status_rules.py`.
2. Implement `run_member` and get `tests/integration/test_end_to_end.py` green.
3. Packet generation: an HTML proof packet (escaped) with highlighted quotes, the monthly table, the clinician statement, and the disclaimer. Optionally convert to PDF.
4. Streamlit app in `app/`: persona picker → status card → evidence → download packet.
5. Run one live demo dry-run with the real LLM, **then record a backup video**.

Split for FINAL: P1A does the evidence-highlighting UI, P1B does status rules and the eval slide, P2 does the packet and reminders.
