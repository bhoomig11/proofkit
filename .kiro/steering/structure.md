---
inclusion: always
---
# ProofKit: structure and ownership

## Modules (import other modules only through their `__init__`)
| Package | Owner | Public API |
|---|---|---|
| `proofkit.extraction` | P1A | `extract_findings(notes, member_id, llm) -> FindingsBundle`, `EXTRACTOR_VERSION` |
| `proofkit.reasoning` | P1B | `decide_exemption(bundle, member, rules, as_of) -> ExemptionDecision`, `draft_statement(decision, bundle, member, llm) -> str`, `load_frailty_rules(path) -> FrailtyRules` |
| `proofkit.wallet` | P2 | `parse_documents(docs, member_id, llm, *, rules=None) -> list[EarningsRecord]`, `evaluate_months(records, rules) -> list[MonthlyCompliance]`, `compute_deadlines(member, rules) -> (verification_months, proof_due_date)`, `build_wallet(member, docs, llm, rules, today) -> WalletResult`, `load_wallet_rules(path) -> WalletRules` |
| `proofkit.integration` | FINAL | `build_status(member, exemption, wallet, today) -> ProofKitStatus`, `run_member(member, notes, docs, llm, frailty_rules_path, wallet_rules_path, today) -> ProofKitStatus` |
| `proofkit.contracts` | FROZEN | pydantic models in `models.py` (the source of truth; `docs/02_CONTRACTS.md` explains them) |
| `proofkit.common` | FROZEN | `llm` (LLMClient, FakeLLM, LLMError), `grounding.locate_quote`, `injection.injection_spans`, `redact.get_logger`, `config` |

- A module imports only `proofkit.contracts`, `proofkit.common` and itself. Only `proofkit.integration` and `app/` import extraction, reasoning and wallet, and only through their public API.
- `FrailtyRules` and `WalletRules` belong to their modules. FINAL passes rule file paths through.
- Never change a public signature. Each module folder holds its own `CLAUDE.md` and `HANDOFF.md`.

## Other folders
- `config/*.json`: rules. `fixtures/`: synthetic personas SYN-0001..0005. `eval/`: P1B metrics. `scripts/`: contract lock, ownership, secret scan.
- `tests/contract/` (frozen), `tests/unit/<module>/`, `tests/acceptance/`, `tests/integration/`.

## Branches and editable paths (from `scripts/check_ownership.py`; fnmatch globs, `*` also matches `/`)
| Prefix | May edit |
|---|---|
| `p1a/` | `src/proofkit/extraction/*`, `tests/unit/extraction/*`, `tests/acceptance/test_extraction_*`, `fixtures/notes/*`, `fixtures/findings/*` |
| `p1b/` | `src/proofkit/reasoning/*`, `tests/unit/reasoning/*`, `tests/acceptance/test_reasoning_*`, `eval/*`, `config/frailty_rules.json`, `fixtures/decisions/*` |
| `p2/` | `src/proofkit/wallet/*`, `tests/unit/wallet/*`, `tests/acceptance/test_wallet_*`, `config/wallet_rules.json`, `fixtures/earnings_docs/*`, `fixtures/earnings/*`, `fixtures/wallet/*` |
| `final/` | `src/proofkit/integration/*`, `app/*`, `tests/integration/*` |
| every owned branch (ANYONE) | `docs/roles/*`, `*/HANDOFF.md`, `README.md`, `setup/TRACKER.md` |

- Any other branch name fails `make check-ownership`. Ask the user to rename it. Never switch branches yourself.
- Run `make check-ownership` before every commit.

## Frozen for everyone
- `src/proofkit/contracts/*`, `src/proofkit/common/*`, `contracts/*` (including `contracts/CONTRACT_LOCK`), `tests/contract/*`, `tests/conftest.py`, `docs/02_CONTRACTS.md`. `CLAUDE.md` is frozen too (CLAUDE.md section 1).
- If a contract looks wrong, stop and tell the user. A change needs all 3 humans to agree and follows the protocol in `docs/05_INTEGRATION.md` (a `contract/<name>` branch, `make lock-contracts`). Prefer additive, optional fields.

## Kiro config
- On `p1a/`, `p1b/`, `p2/` and `final/` branches, the only `.kiro/` path that may change is `.kiro/specs/*`.
- `.kiro/steering/`, `.kiro/hooks/`, `.kiro/agents/` and `.kiro/settings/` change only on `main`.
- `.kiro/hooks/guard_tools.py` enforces this. On every branch it also blocks writes to FROZEN paths and `.git/`, and any `.env` path.
