# P1B: Exemption Reasoning + Evaluation

## Mission
Turn findings into an **auditable, deterministic exemption decision**, draft the clinician's statement, and produce the **accuracy numbers** that make our backend credible on stage.

## You own (may edit)
`src/proofkit/reasoning/**` · `tests/unit/reasoning/**` · `tests/acceptance/test_reasoning_*.py` · `eval/**` · `config/frailty_rules.json` · `fixtures/decisions/**`

## You must NOT
- Edit contracts, common, conftest, CLAUDE.md, or another module's code or tests.
- Import `proofkit.extraction` (use the golden findings fixtures) or `proofkit.wallet`.
- Let an LLM influence `outcome`. `decide_exemption` has no LLM parameter, on purpose.

## Interface
```python
load_frailty_rules(path: Path) -> FrailtyRules                       # strict pydantic, internal to you
decide_exemption(bundle, member, rules, as_of: date) -> ExemptionDecision   # pure
draft_statement(decision, bundle, member, llm) -> str                # LLM task "draft_statement" → {"summary": str}
```

## Decision algorithm (spec it, then build it)
1. `bundle.member_id != member.member_id` → `ValueError`.
2. Keep findings with `as_of − lookback_months ≤ note_date ≤ as_of` (inclusive; use calendar months).
3. Drop findings with `confidence < min_finding_confidence`.
4. Match each remaining finding to rules by **ICD-10 prefix on code boundaries**: `F31` matches `F31.9`; prefix `F32.2` matches `F32.2` but `F32.9` matches nothing. Compare uppercase strings.
5. Status `current` + confidence ≥ `review_band.high` → **counts**. `current` within `[low, high)`, or status `uncertain` on a matching rule → **review**.
6. Any counting match → EXEMPT (type from the rule; `matched_rules` grouped per rule; **all** counting evidence IDs listed). Else any review → NEEDS_CLINICIAN_REVIEW with human-readable reasons. Else NOT_EXEMPT.
7. `confidence` of the decision = max counting finding confidence (or a documented formula). `rules_version` comes from config.
8. Output is sorted deterministically (rule_id, finding_id).

## Statement drafter
- A fixed template: header, member display name + ID, as-of date, each piece of evidence as `ICD-10 — condition — "quote" (note_id, date)`, the matched rule labels, the LLM summary paragraph, a signature block, and the sentence **"This statement must be reviewed and signed by a licensed clinician."**
- Validate the LLM summary: reject it if it contains an ICD-10-like code not in the evidence, or a condition name from any rule label that isn't in the evidence. Fallback: a template-only summary.
- `NOT_EXEMPT` → `ValueError`.

## Eval (your pitch slide, `eval/run_eval.py`)
- Offline: decision accuracy on fixtures (should be 100%; it's the regression check).
- Live: real LLM extraction vs golden labels → finding precision/recall/F1, **status accuracy** (the headline), injection resistance, and decision accuracy.
- Grow the labeled set to 15–20 notes with P1A, including at least 5 tricky negation/r-o/family-history cases and 2 injection cases.

## TDD order (`tests/unit/reasoning/test_reasoning_spec.py`)
1. `test_rules_load_and_reject_bad_config`
2. `test_current_qualifying_condition_is_exempt`, `test_no_findings_is_not_exempt`, `test_member_mismatch_raises`
3. `test_non_current_statuses_never_count`, `test_uncertain_qualifying_condition_goes_to_review`
4. `test_lookback_window_is_inclusive_and_excludes_older`, `test_future_dated_findings_ignored`
5. `test_confidence_band`, `test_prefix_matching_respects_code_boundaries`
6. `test_strongest_evidence_wins_and_all_matching_evidence_listed`, `test_deterministic`
7. Statement: `test_statement_uses_llm_summary_and_cites_quotes`, `test_statement_rejects_llm_summary_that_invents_conditions`, `test_statement_refused_for_not_exempt`
8. Acceptance `tests/acceptance/test_reasoning_golden.py`
9. Eval metrics: write `tests/unit/reasoning/test_eval_metrics.py` first

## Extra tests you should add
- [ ] lookback with month-end dates (Mar 31 − 1 month)
- [ ] lookback_months varied 6 / 12 / 24 → show the effect on Priya's PTSD note (great pitch point: "lookback is the most significant parameter")
- [ ] multiple rules matched → one decision, all rules listed
- [ ] statement escaping: quotes containing `<script>` come out escaped if you render HTML
- [ ] rules config: duplicate rule_id or empty prefixes rejected

## Checklist
- [ ] Spec + acceptance green
- [ ] `decide_exemption` has zero imports of `proofkit.common.llm`
- [ ] Statement validated + fallback tested
- [ ] Eval offline + live numbers in a markdown table
- [ ] Coverage ≥ 85% for `reasoning/`
- [ ] Every rule in config still has `"verify": true`, and the README says it's a seed list
- [ ] `/security-check` clean, `/handoff` done

## Claude Code kickoff prompt
```
I am P1B (reasoning + eval) on ProofKit. Read CLAUDE.md, docs/02_CONTRACTS.md, docs/roles/P1B_REASONING.md,
docs/03_TDD_WORKFLOW.md, docs/04_SECURITY.md, src/proofkit/reasoning/CLAUDE.md and config/frailty_rules.json.
Run `make check-contracts` and `make test-p1b`; summarise what is red.
Propose the FrailtyRules model and the decision algorithm as pseudocode, and the order you'll turn spec tests green.
No implementation until I say OK. Then strictly test-first with /tdd, showing red output before each change.
Never import proofkit.extraction; use fixtures/findings/*.golden.json.
```
