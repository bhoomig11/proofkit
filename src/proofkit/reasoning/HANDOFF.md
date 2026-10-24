# HANDOFF: reasoning (P1B)

## What works
- `load_frailty_rules(path) -> FrailtyRules`: strict loader for `config/frailty_rules.json`. Rejects unknown keys, duplicate
  `rule_id`s, empty or malformed ICD-10 prefixes, `exemption_type: none`, and an inverted review band. `_`-keys are comments.
- `decide_exemption(bundle, member, rules, as_of) -> ExemptionDecision`: pure and deterministic (no LLM, clock, or I/O;
  enforced by `tests/unit/reasoning/test_purity.py`).
  1. `bundle.member_id != member.member_id` -> `ValueError`.
  2. Keep findings with `as_of - lookback ≤ note_date ≤ as_of` (calendar months, inclusive, day clamped: Mar 31 - 1 mo = Feb 28).
  3. Drop findings with `confidence < min_finding_confidence` (0.6).
  4. Match rules by ICD-10 prefix on code boundaries (`F31` matches `F31.9`; `F32.2` does not match `F32.9`).
  5. `current` and confidence ≥ 0.8 -> counts. `current` in [0.6, 0.8) or `uncertain` -> clinician review. Other statuses never count.
  6. Any count -> **EXEMPT** (all counting evidence, rules grouped, confidence = max). Else any review ->
     **NEEDS_CLINICIAN_REVIEW** (`exemption_type=none`, no `matched_rules`, reviewed findings as evidence, readable
     `review_reasons`). Else **NOT_EXEMPT** (`confidence=0.0`).
- `draft_statement(decision, bundle, member, llm) -> str`: fixed plain-text template (≤ 5000 chars, sign-off never cut).
  The LLM writes only the summary paragraph (task `draft_statement` -> `{"summary": str}`); evidence goes through
  `untrusted_text`. The summary is rejected (template fallback) if it is missing or too long, names an ICD-10 code outside
  the evidence (any case, with or without the dot), names a condition from a rule the evidence does not match (rule `terms`
  in the config), or makes an eligibility claim (exempt / eligible / qualifies / frail / MassHealth / Medicaid).
  `NOT_EXEMPT` -> `ValueError`.
- `eval/run_eval.py` (`make eval`): finding P/R/F1 on (note, 3-char ICD category, status), status accuracy (+ confusion),
  decision accuracy (+ confusion), injection resistance, and a 6/12/24-month lookback sweep. Markdown table + JSON in
  `eval/results/` (gitignored). Offline = golden findings (100%, regression check).

## How FINAL calls it
```python
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules
rules = load_frailty_rules(Path("config/frailty_rules.json"))
decision = decide_exemption(bundle, member, rules, as_of=today)
if decision.outcome != DecisionOutcome.NOT_EXEMPT:
    decision = decision.model_copy(update={"statement_draft": draft_statement(decision, bundle, member, llm)})
```
Sample outputs for all 5 personas: `fixtures/decisions/*.decision.generated.json` (regenerate locally; gitignored).

## What FINAL needs to know
- **Escape the statement and review reasons before rendering HTML.** They are plain text and contain quotes from notes.
- `NEEDS_CLINICIAN_REVIEW` never carries an `exemption_type` or `matched_rules`; use `review_reasons` for the action item.
- `draft_statement` loads rule labels/terms from the default `config/frailty_rules.json` (its signature has no rules arg).

## Known limits
- The rule list is a **seed**: every rule and the 12-month lookback are `"verify": true` and must be checked against
  MassHealth/CMS guidance before real use. Condition `terms` are a hand-made vocabulary, not exhaustive.
- Live eval needs real extraction output. P1B code doesn't import `proofkit.extraction`: save one `FindingsBundle` JSON per
  member to a folder and run `python eval/run_eval.py --predictions <folder>`. `--live` prints these instructions.
- The ICD-code check in summaries is conservative: lab names that look like codes (e.g. "A1C", "B12") cause a template fallback.
- 10 more synthetic labeled notes are drafted (not committed) for P1A to review; they add 3 adversarial cases and a visible
  lookback effect (a 9-month and an 18-month current finding).
