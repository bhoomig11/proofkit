# 01: Architecture and ownership

```
                ┌─────────────────────── P1A ───────────────────────┐   ┌──────────────── P1B ────────────────┐
 clinical notes │ extraction.extract_findings(notes, llm)           │   │ reasoning.decide_exemption(bundle,  │
 (untrusted) ──▶│  segment → LLM extract → normalize ICD-10 →       │──▶│   member, rules, as_of)             │
                │  assign status (current/ruled_out/negated/...) →  │   │  deterministic rule match →         │
                │  GROUND every quote (offsets) → FindingsBundle    │   │  lookback → confidence → decision   │
                └───────────────────────────────────────────────────┘   │ reasoning.draft_statement(decision) │
                                                         FindingsBundle │   (LLM-assisted, template-bound)    │
                                                                        └──────────────┬──────────────────────┘
                                                                                       │ ExemptionDecision
                ┌──────────────────────── P2 ───────────────────────┐                  ▼
 earnings docs  │ wallet.parse_documents(docs, llm) → EarningsRecord │      ┌────────── FINAL ──────────┐
 (untrusted) ──▶│ wallet.evaluate_months(records, rules) →           │─────▶│ integration.build_status()│──▶ ProofKitStatus
                │   MonthlyCompliance  (deterministic)               │      │ → proof packet + UI       │     + packet PDF
                │ wallet.compute_deadlines(member, rules)            │      └───────────────────────────┘
                └────────────────────────────────────────────────────┘ WalletResult
```

## Design principles (apply to every module)
1. **Contract-first.** Modules talk only through pydantic models in `src/proofkit/contracts/models.py`. That file is frozen.
2. **The LLM extracts, code decides.** The LLM reads text and proposes structured data. Deterministic, tested Python decides "exempt" and "qualifies."
3. **Everything is grounded.** Every finding and every earnings record points back to an exact quote or position in its source.
4. **Dependency injection for all boundaries.** Functions take an `LLMClient`, a `today`/`as_of` date, and a rules config as parameters. No globals, so tests stay deterministic.
5. **Failing safe.** When unsure → `needs_clinician_review` / `needs_review`. Never a silent "exempt" or "qualifies".

## Ownership map
| Path | Owner |
|---|---|
| `src/proofkit/contracts/`, `contracts/CONTRACT_LOCK` | **FROZEN** (all 3 must agree) |
| `src/proofkit/common/` (llm, grounding, redact, config) | **FROZEN** (pre-built, tested) |
| `src/proofkit/extraction/` | P1A |
| `src/proofkit/reasoning/`, `eval/`, `config/frailty_rules.json` | P1B |
| `src/proofkit/wallet/`, `config/wallet_rules.json` | P2 |
| `src/proofkit/integration/`, `app/` | FINAL (all) |

## Public APIs (each module's `__init__.py` exports exactly these)
```python
# P1A
extract_findings(notes: list[ClinicalNote], member_id: str, llm: LLMClient) -> FindingsBundle

# P1B
decide_exemption(bundle: FindingsBundle, member: Member, rules: FrailtyRules, as_of: date) -> ExemptionDecision
draft_statement(decision: ExemptionDecision, bundle: FindingsBundle, member: Member, llm: LLMClient) -> str
load_frailty_rules(path: Path) -> FrailtyRules

# P2
parse_documents(docs: list[EarningsDocument], member_id: str, llm: LLMClient) -> list[EarningsRecord]
evaluate_months(records: list[EarningsRecord], rules: WalletRules) -> list[MonthlyCompliance]
build_wallet(member: Member, docs: list[EarningsDocument], llm: LLMClient, rules: WalletRules, today: date) -> WalletResult
load_wallet_rules(path: Path) -> WalletRules

# FINAL
build_status(member, exemption: ExemptionDecision | None, wallet: WalletResult | None, today) -> ProofKitStatus
```
`FrailtyRules` and `WalletRules` are **internal** to their modules (owner defines them). FINAL only passes file paths through.
