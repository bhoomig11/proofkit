# How we used Kiro (RenewRight)

RenewRight is the submission name. The repo, package and contracts still use the working name ProofKit (`proofkit`).

## Summary (5 bullets)

- The three core modules (P1A extraction, P1B reasoning, P2 wallet) were built first with Claude Code, test-first. Kiro was not used for them.
- Kiro came in on 2026-10-24 for the FINAL phase and follow-ups: SMS reminder, PDF uploads, offline demo mode, a fictional-brand rename, an HTML proof packet, an MCP server (RED merged on its branch only), and the `.kiro/` steering, hooks and agents.
- Two Kiro surfaces: the IDE in spec mode built the proof packet; CLI 2.34 ran headless RED/GREEN jobs with least-privilege custom agents. Kiro never committed or pushed.
- Hypothesis property tests written by Kiro found 2 real bugs in already-merged wallet code that 143 unit tests had passed.
- A read-only `security-reviewer` agent on a different model (`gpt-5.6-sol`) found 6 HIGH and 2 MEDIUM issues across SMS and demo mode, including one HIGH introduced by a fix. All were fixed test-first. The packet findings are a parked follow-up.

## Honest timeline: what was built with what

- The core modules (P1A extraction, P1B reasoning, P2 wallet) were built first with Claude Code, test-first, under a shared `CLAUDE.md` kept out of git. Their commits carry no Kiro trailer.
- Kiro came in for the FINAL phase and the follow-ups on 2026-10-24.
- In the CLI work, a Claude Code session orchestrated headless Kiro CLI jobs. It wrote each prompt, re-ran every RED and GREEN test itself, and committed as Karthik with `Built-with:` trailers (for example `Built-with: Kiro CLI (claude-opus-5.5)` in `721ca8f`). Kiro jobs never committed or pushed; the lane agents deny `git commit` and `git push`.
- Commits with a `[kiro]` subject mark the tool, not the committer. All of them are authored by Karthik.

| Component | Phase | Tool | Evidence |
|---|---|---|---|
| P1A extraction | core | Claude Code (arshmehar) | `d2a0476`..`e35d76d`, no Kiro trailer |
| P1B reasoning + eval | core | Claude Code (Bhoomika) | `92ec70d`..`b1e8966`, no Kiro trailer |
| P2 wallet | core | Claude Code (Dhruv) | `d11fe27`..`3c67c2d`, no Kiro trailer |
| `build_status`, `run_member`, Coverage Coach | FINAL | Bhoomika; tool not stated in commits | `0b0528a`, `ae9014b` |
| `.kiro/steering`, hooks, MCP config, reviewer agents | FINAL | Kiro CLI drafted, human saved | `c59d5ec` |
| RED/GREEN lane agents | FINAL | hand-written | `3f168c6` |
| Dependency pins, ownership rule for `.kiro/specs` | FINAL | Kiro CLI (`main-foundation`) | `b2cd35f`, `96d8b24` |
| PDF uploads, bomb-proof decoding, month split | follow-up | Kiro CLI, spec `pdf-uploads` | `610bc32` (RED), `140e752` (GREEN) |
| SMS reminder | FINAL | Kiro CLI, spec `sms-reminder` | `52b4287` (spec), `af64371`, `a100e7d`, `7cc1d9c` (RED), `c821a44` (GREEN) |
| Fictional gig platforms | follow-up | Kiro CLI | `798eb07` (RED), `166eeb7` (refactor) |
| Offline demo mode | FINAL | Kiro CLI, spec `offline-demo` | `5c3aa6c` (spec), `c118c3d`, `e060ac7`, `6176ebe` (RED), `86b7180` (GREEN) |
| HTML proof packet (`render_packet`) | FINAL | Kiro IDE spec mode, spec `proof-packet` | `26e45f8`, renamed in `db1e602`, merged `a379a00`, exported `9464046` |
| RenewRight MCP server | follow-up | Kiro CLI RED/GREEN agents | `721ca8f` (RED) on `final/karthik-mcp`; GREEN not yet committed |
| Coverage Copilot UI (`app/`, `packet.py`) | FINAL | Kiro spec, then Claude Code | `c663854`, `.kiro/specs/final-ui/context.md` |

Notes on `main`:

- `main` has two packet renderers. `src/proofkit/integration/packet.py` is Bhoomika's `build_packet_html` (`c663854`), which the UI uses. The Kiro IDE renderer collided with it add/add, so it was moved with `git mv` to `proof_packet.py` (`db1e602`; only the 10 test import lines changed, no assertions) and merged (`a379a00`). The full non-live suite on `main` is 774 passed (team figure; not re-run for this write-up).
- The `final-ui` journal's last entry reads "RESUMED 2026-10-24 (Claude Code, 1-hour timebox; Kiro was too slow for the deadline)". The spec and UI tasks 1 to 3 came from the earlier session, which the journal implies was Kiro without naming the surface. Not verified beyond that file.

## 1. Which Kiro tools did we use, and how did they differ?

- IDE (spec mode): built the proof packet. Requirements, design and tasks were reviewed interactively phase by phase. The IDE may write under `.kiro/`, and it generated a formal correctness-property section and Hypothesis tests from it. It reported 15/15 tasks done and 46 packet tests (`26e45f8`).
- CLI 2.34 headless: `kiro-cli chat --v3 --no-interactive --agent <name>`. Parallel lanes ran in separate git worktrees (one per branch: SMS, PDF, demo, rename, MCP, i18n). Each job used a least-privilege custom agent from `.kiro/agents/`, and we audited its stream-json log. Headless CLI cannot write under `.kiro/` without `--trust-all-tools`, which we chose not to use. Plain `--trust-tools` is denied in V3 headless mode. Permission globs match the whole command line, so `git status` needs a trailing `*`.
- Web: not used. It needs a paid plan; we had KIRO FREE plus the 2,000-credit hackathon bonus.
- Crew: not used.

| | IDE spec mode | CLI headless |
|---|---|---|
| Better at | Turning a feature into EARS requirements and numbered correctness properties, with a human approving each phase | Running several features at once, scripted by an orchestrator, one task per job |
| Guardrails | Hooks plus the human reviewer | Per-agent allow-lists for paths and commands, plus hooks |
| Writes under `.kiro/` | Yes | No (drafts saved by a human) |
| Audit trail | The IDE session (not stored in repo) | stream-json logs and commit bodies with RED/GREEN counts |
| Weak spot | One feature at a time; its renderer collided with parallel UI work | No interactive review; needs every allowed command spelled out in advance |

How one headless job ran:

1. Claude Code wrote the prompt for one spec task and started `kiro-cli chat --v3 --no-interactive --agent <lane>-red`.
2. Kiro wrote the failing tests. Claude Code re-ran them to confirm they failed for the right reason, then committed `test: ... RED [kiro]`.
3. The same steps ran with `<lane>-green`. Claude Code re-ran the module suite before committing `feat:` or `fix:`.
4. `security-reviewer` read the diff. Findings that were fixed got new RED tests before the fix.

Custom agents (`.kiro/agents/`, 8 files):

- `sms-red`, `p2-pdf-red`: may write only tests and fixtures.
- `sms-green`, `p2-pdf-green`: may write only source and config, so a GREEN agent cannot weaken a test.
- `security-reviewer` and `kiro-config-author`: no shell.
- `main-foundation`: may write only `scripts/check_ownership.py` and `pyproject.toml`. `p2-verify`: only `setup/TRACKER.md`.
- Every agent denies `.env` reads. Lane agents also deny `git commit`, `git push`, other git writes and recursive deletes.
- The demo, rename and MCP jobs have no agent files on `main`; which agent ran them is not verified from the repo.

## 2. Spec-driven development

Specs in `.kiro/specs/`, each with `requirements.md`, `design.md` and `tasks.md`:

| Spec | Author | Produced |
|---|---|---|
| `proof-packet` | Kiro IDE | `render_packet` in `proof_packet.py`, 46 tests incl. properties (`26e45f8`) |
| `sms-reminder` | Kiro CLI | `sms_reminder` (`c821a44`) |
| `pdf-uploads` | Kiro CLI | PDF uploads, bomb-proof decoding, exact month split (`140e752`) |
| `offline-demo` | Kiro CLI | `proofkit.integration.demo` (`86b7180`) |
| `final-ui` (plus `context.md` journal) | Bhoomika's session | Coverage Copilot UI (`c663854`) |

Structure:

- Requirements are EARS-style ("WHEN ... THE Renderer SHALL ...", "WHILE the installed pypdf is older than 6.21.2, THE wallet SHALL NOT ...") with numbered acceptance criteria under user stories.
- Each design has a correctness-properties section mapped back to requirements. `proof-packet/design.md` lists Properties 1 to 10, each with "Validates: Requirements ...". `sms-reminder` maps P1 to P12 to R1 to R7 and to named tests. `pdf-uploads` maps P1 to P10 to R1 to R4 and records the RED counterexamples.
- Tasks put tests first. `pdf-uploads` also has an explicit human-decision task (task 7: what to do with more than 744 h in a month).
- `96d8b24` made `.kiro/specs/*` the only `.kiro/` path an owned branch may change, so specs ride with their feature branch.

How specs made RED/GREEN mechanical: the orchestrator handed Kiro one numbered task per job ("RED: ..." to a `-red` agent, "GREEN: ..." to a `-green` agent). Each property row names its test, so "is RED done" became "do these named tests exist and fail for the right reason". Recorded results:

| Job | RED | GREEN |
|---|---|---|
| SMS reminder | 20 example tests and 9 properties fail on the missing module (`af64371`) | 87 example and Hypothesis tests pass (`c821a44`) |
| PDF uploads + split | 12 new tests fail, 144 pass (`610bc32`) | test-p2: 156 passed, 97% wallet coverage (`140e752`) |
| Fictional platforms | 6 fail, 2 pass (`798eb07`) | test-p2: 165 passed, 97% coverage, ruff clean (`166eeb7`) |
| Offline demo | fails on missing `proofkit.integration.demo` (`c118c3d`) | 19 demo tests pass, 106 with the reminder suites (`86b7180`) |
| MCP server | 271-line test file (`721ca8f`) | 28 tests green (team figure; GREEN not committed yet) |

Spec vs vibe coding, from this project:

- Specs paid off where correctness was subtle. The month-split properties came straight from `pdf-uploads` R4 and found 2 bugs. The SMS spec surfaced a real conflict with steering (dollar amounts) before any code was written.
- Specs cost time and drifted. `sms-reminder/tasks.md` leaves GREEN tasks 4 to 7 unticked although `c821a44` implements them. `offline-demo/tasks.md` has no ticks, and its task 8 still describes the "(most items, id) tie-break" that `86b7180` replaced as unsafe. In `final-ui/tasks.md`, parent tasks 1 to 8 are ticked but not their subtasks.
- The last hour of the UI was closer to vibe coding: per the journal, Claude Code finished it in a 1-hour timebox without spec updates.
- The core modules used role docs with a TDD order (`docs/roles/`), not Kiro specs, and still reached 143 P2 tests. They missed the two edge cases that property-mapped specs caught.

## 3. Agent hooks

All files in `.kiro/hooks/` use Kiro's v1 schema.

- `guard.json` (trigger `PreToolUse`, command `python .kiro/hooks/guard_tools.py`). It loads `FROZEN`, `OWNED` and `ANYONE` from `scripts/check_ownership.py`, so the hook and `make check-ownership` share one source of truth. It blocks git write commands, recursive deletes, network uploads, `.env` paths, writes to `.git/` and FROZEN paths, and writes outside the branch's owned paths. Exit 2 blocks the call, and it fails closed if it cannot load the rules.
  - End-to-end scratch-repo test: a frozen-path write, a `.env` read and `git commit` were blocked with exit 2; an owned write was allowed (`c59d5ec`).
  - Real runs: 486 allowed calls and 0 blocks, because the agents' permission rules refused risky commands first. The guard was a backstop that never had to fire.
  - Real permission denials per run: 4 and 8 in the PDF lane's RED and GREEN, and 3 in the SMS lane's RED. Examples: `python -c` and an inline PowerShell script, refused because lane allow-lists contain only `.venv/Scripts/python -m pytest*`, `git status*` and `git diff*`.
- `tests-on-save.json` (trigger `PostFileSave`). Saving `src/proofkit/wallet/*.py` runs `tests/unit/wallet`; saving `src/proofkit/integration/*.py` runs `tests/integration -k "not end_to_end"`. Both go through `run_tests.py`, a cross-platform launcher that finds `.venv/Scripts` or `.venv/bin`. It gave immediate red/green feedback on save; no specific catch is recorded.
- `stop-checks.json` (trigger `Stop`). Runs `scripts/check_ownership.py` and `scripts/scan_secrets.py` as two separate hooks, because Windows PowerShell 5.1 has no `&&`. No recorded failure.
- `escape-review.json` (trigger `PostFileSave` on `integration/packet.py` or `integration/reminder.py`, action type `agent`). It checks three things without editing: HTML escaping, SMS length and charset, and PHI beyond the first name. The `final-ui` journal records that it fired on Bhoomika's `packet.py` save and that its three checks were addressed by hand (escaping: no finding). Its matcher does not cover `proof_packet.py`.

Kiro once wrote a hook file in the wrong schema; it was rewritten by hand into the v1 format (`c59d5ec`).

## 4. Steering docs

7 files in `.kiro/steering/`:

| File | Inclusion |
|---|---|
| `product.md`, `tech.md`, `structure.md`, `security.md`, `tdd.md` | `always` |
| `wallet.md` | `fileMatch`: wallet source, wallet tests, wallet acceptance tests, `config/wallet_rules.json` |
| `integration.md` | `fileMatch`: `src/proofkit/integration/**`, `app/**`, `tests/integration/**` |

Kiro drafted them from the gitignored `CLAUDE.md` and `docs/` (`c59d5ec`), so Kiro jobs got the same rules as the Claude Code sessions.

The strategy that mattered most: encode the team's ownership map (which branch prefix may edit which paths), the security rules (untrusted text only via `untrusted_text`, grounding, no `.env`), and the TDD loop as always-on steering, and keep module rules file-matched. A Kiro job on any lane started with the frozen paths and the RED/GREEN rules already in context.

Conflicts we hit:

- The SMS spec and steering disagreed on whether an AT_RISK message may state a dollar amount. The `gpt-5.6-sol` reviewer flagged it as HIGH. It was resolved by a product decision (Karthik: "$60.00 short" is allowed), and steering was updated in its own commit (`86749cc`).
- Drift: `tech.md` still lists `pypdf==5.1.0`, and `wallet.md` still says PDF stays off until the bump. `pyproject.toml` pins `pypdf==6.21.2`, and PDF uploads were re-enabled in `140e752`. Steering only changes on `main`, and nobody updated it.

## 5. MCP

- Playwright MCP 0.0.83 is configured in `.kiro/settings/mcp.json` (`npx -y @playwright/mcp@0.0.83 --headless`, empty `env`, no credentials). It was NOT exercised in any recorded run. The `final-ui` journal lists "Playwright browser run + ui-test-report.md" under "Not done"; the UI was smoke-tested with Streamlit's `AppTest` instead (`tests/integration/test_ui_app.py`).
- RenewRight as an MCP server: `src/proofkit/integration/mcp_server.py` on branch `final/karthik-mcp`. It is stdlib JSON-RPC over stdio with 5 read-only tools: `list_members`, `member_status`, `wallet_months`, `sms_reminder`, `triage`. It runs offline through `demo_llm`. It was built test-first by Kiro CLI RED/GREEN agents. The RED commit (`721ca8f`) covers the initialize handshake, tool schemas, each persona's status, Dev's $60 shortfall and SMS, triage order, errors without tracebacks, JSON-RPC errors, a subprocess stdio round trip, no sockets and no note quotes. 28 tests are green (team figure). The GREEN implementation exists in the branch worktree but is not committed yet.
- Pending: registration in `.kiro/settings/mcp.json` and a Kiro navigator agent that calls the server. Neither is on `main` (`mcp.json` on `main` lists only Playwright).
- What this enables: Kiro, or any MCP client, can triage members and draft SMS reminders through tools, without reading notes or documents.

## 6. Property-based testing

`hypothesis==6.170.9` was pinned with team approval (`b2cd35f`).

Bugs found, both in already-merged code that 143 P2 unit tests had passed (`610bc32`):

1. $0.02 over 91 days produced a -$0.01 month piece. The contract rejected it, and the whole statement was silently dropped.
2. 768.01 h over 32 days put 744.01 h in January, over the 744 h monthly cap, so the statement was dropped. The product decision was to keep statements over 24 h/day and flag them for review, not cap them.

Fixes in `140e752`: largest-remainder allocation in whole cents and hundredths of an hour; statements over 24 h/day kept with `hours=None` and flagged. `src/proofkit/wallet/HANDOFF.md` documents both.

Property suites:

- Wallet split, `tests/unit/wallet/test_split_properties.py`, 200 examples each: never dropped, each piece inside one calendar month, contiguous coverage, quote kept, exact income and hours, the over-24-h/day rule. Requirements: `pdf-uploads` R4.1 to R4.5.
- SMS, `tests/integration/test_reminder_properties.py`, 300 examples each: at most 160 printable-ASCII characters, greeting is the folded first name only, output invariant under member ID, phone, later name words, conditions and exemption type. Requirements: `sms-reminder` R1 to R4 (design P1 to P8).
- Proof packet, `tests/integration/test_packet_properties.py`, 100 examples each, from the IDE spec: Property 3 (capability confinement: fixed CSP, no `<script>`, no `on*` attributes), 5 (merged highlights exactly cover valid evidence), 7 (missing-note evidence preserved and labelled), 10 (byte-deterministic output). Requirements include 1.2, 3.4, 5.1 to 5.6, 6.1 to 6.4 and 12.2 to 12.6.
- Rename guard (`798eb07`): not randomized, but an invariant test that scans P2 files, including decoded PDF fixtures, for real gig-platform brands.

Not done: `offline-demo` task 15 (properties) and `pdf-uploads` task 6 (CSV split properties).

## 7. Kiro powers

- We evaluated the registry (Datadog, Dynatrace, Figma, Neon, Netlify, Postman, Supabase, Stripe, Strands SDK, AWS Aurora). None fit a Python + Streamlit Medicaid tool, so none were installed.
- A custom power, `powers/renewright-navigator`, packaging the RenewRight MCP server and a navigator-triage skill, was drafted, not yet imported or validated. `powers/` is not in git on `main` or in the MCP worktree.
- Third-party tooling: the `gpt-5.6-sol` model through Kiro as an independent, read-only `security-reviewer` (no shell, reports HIGH/MEDIUM/LOW against `docs/04_SECURITY.md`). The code was written by a different model. Findings:
  - SMS: 3 HIGH, fixed. The greeting could leak IDs such as "SYN-0004", there was no member-ID check, and spec and steering conflicted over dollar amounts. A LOW on decimal context was also fixed (`a100e7d`, `7cc1d9c`, `86749cc`, `c821a44`).
  - Demo mode: 2 HIGH and 2 MEDIUM, fixed (`e060ac7` RED). A re-review found a new HIGH that the fix introduced: containment matching picked the source with the most items, so 36 cross-member note pairs leaked another member's golden evidence (`6176ebe`). Fixed by requiring an exact match or exactly one contained source (`86b7180`).
  - Rename: none (`166eeb7`).
  - Proof packet: escaping and CSP clean. A member-ID check and the fixed disclaimer are a known follow-up (RED tests `513a751`, reverted in `c7bb2cc`, parked on `final/karthik-packet-isolation`).
- Also from the PDF lane: pypdf 6.21.2 alone accepted a 200 MB FlateDecode bomb; decoding now runs under output caps equal to `max_bytes` (`140e752`). After the pin bump, pip-audit went from 60 pypdf advisories and 1 python-dotenv advisory to 0 (`b2cd35f`).

## 8. Credits and models

- Credits: 487.74 of 2,000 used on Karthik's account (KIRO FREE plus hackathon bonus) so far. To be refreshed at the end. Teammates' usage is not included.
- `claude-opus-5.5` (2x credits) ran the builders: lane agents, config author, foundation, verify.
- `gpt-5.6-sol` (4.4x credits) ran only the reviews.

## 9. What surprised us, and Kiro limits we hit

- Headless CLI refuses writes under `.kiro/`. Kiro drafted steering, hooks and specs; a human saved them after review (`c59d5ec`).
- `--trust-tools` is denied in V3 non-interactive mode, so every allowed tool and command lives in the agent files. `kiro-cli agent validate` caught config errors in them.
- Permission globs match the whole command line; a prefix needs a trailing `*`.
- Least-privilege agents did the real blocking (15 denials across three runs). The guard hook never fired in practice.
- The guard's git-write rule is coarse: while writing this file, it blocked a read-only `git worktree list`.
- Kiro wrote a hook in the wrong schema; the Playwright pin and the Stop-hook split were also fixed by hand (`c59d5ec`).
- A security fix introduced a new HIGH (demo cross-member leak). Only the re-review caught it.
- Spec checkboxes and steering fell behind the code (sections 2 and 4).
- Per the `final-ui` journal, Kiro was too slow for the last UI hour, so that work finished in Claude Code.

## 10. Teammates' Kiro usage

### Bhoomika (Coverage Copilot UI, login, demo link): TO BE FILLED BY BHOOMIKA

Files that exist: `.kiro/specs/final-ui/requirements.md`, `design.md`, `tasks.md`, `context.md`.

- Kiro surface used and for which tasks: TO BE FILLED
- What the `final-ui` spec and hooks produced or caught: TO BE FILLED
- Where Kiro was dropped for Claude Code and why: TO BE FILLED

### Arsh (extraction, voice chatbot): TO BE FILLED BY ARSH

- Kiro surface used and for which tasks: TO BE FILLED
- Specs, hooks or steering involved: TO BE FILLED
- Evidence (commits or files): TO BE FILLED

## Known follow-ups

- Commit the MCP server GREEN, register it in `.kiro/settings/mcp.json`, add the navigator agent, and merge `final/karthik-mcp`.
- Import and validate the `renewright-navigator` power.
- Proof packet member isolation: member-ID check and fixed disclaimer. RED tests and an unverified, interrupted GREEN attempt (`b2195d4`) are on `final/karthik-packet-isolation`. Switching the UI download button to `render_packet` is optional.
- Remaining real brand names: `scripts/build_fixtures.py`, `docs/00_CONTEXT.md`, `docs/06_TIMELINE.md`, `docs/roles/P2_WALLET.md`, one UI string, and the frozen contract example and contract tests (`166eeb7`).
- Wire `choose_llm` (demo mode) and `sms_reminder` into the app. The `final-ui` journal lists SMS as "OUT (unmerged branch)"; the app has its own offline replay in `app/offline.py`.
- Spec work: `offline-demo` task 15 and syncing tasks 8 and 15; `pdf-uploads` task 6 (CSV properties); tick completed tasks in `sms-reminder` and `final-ui`.
- Update `tech.md` and `wallet.md` steering for `pypdf==6.21.2` and PDF uploads being on.
- Run a recorded Playwright MCP pass and write `.kiro/specs/final-ui/ui-test-report.md`.
- Refresh the credit figure.
