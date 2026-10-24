# HANDOFF: extraction (P1A)

## What works
`extract_findings(notes, member_id, llm) -> FindingsBundle` turns `ClinicalNote[]` into grounded, statused findings.
For each note it makes one LLM call (task `extract_findings`) and then verifies every proposed finding:

1. **Member check:** any note for another member -> `ValueError` (nothing is called).
2. **LLM call:** note text goes only through `untrusted_text=`; instructions are the static `prompts.py` text.
   Any client failure (LLMError, timeout, API error, malformed reply) is retried once, then the note is skipped
   (left out of `notes_processed`). Only the note_id and the error type are logged.
3. **Per finding** (dropped and counted in `dropped_ungrounded` if it fails):
   - ICD-10 normalised (`m329` -> `M32.9`) and checked against the contract pattern.
   - `condition` must be plain single-line text, no markup, nothing that looks like an instruction.
   - `confidence` must be a real number (a bool or string is rejected).
   - The quote is re-located in the note with `locate_quote`; the stored quote and offsets are the original slice.
   - Quotes overlapping text flagged by `injection_spans` are dropped.
4. **Status backstop** (`status.py`): sentence-scoped NegEx-style cues can only make a status more cautious
   (current -> negated / ruled_out / family_history / historical / uncertain). It never upgrades to current and
   never overrides a non-current LLM status.
5. **Code/quote consistency** (`consistency.py`): a current finding whose code matches a frailty rule must have one of
   that rule's `terms` in its sentence, otherwise it becomes `uncertain` (clinician review). This stops a mis-coded but
   grounded quote (e.g. F20.9 on "right ankle sprain") from counting toward an exemption.
6. **Assemble:** dedupe identical (icd10, span), IDs `F-{note_id}-{i}` in quote order, `extractor_version`.

## How to call it
```python
from proofkit.common.llm import AnthropicClient
from proofkit.extraction import extract_findings
bundle = extract_findings(notes_for_member, member.member_id, AnthropicClient())
# bundle.findings: every quote == note.text[quote_start:quote_end]
```
Pass the bundle straight to P1B: `decide_exemption(bundle, member, rules, as_of)`.

## Evidence
- `make test-p1a`: 128 passed, 99% coverage of `extraction/`.
- Spec: `tests/unit/extraction/test_extraction_spec.py` (12). Acceptance: `tests/acceptance/test_extraction_golden.py`.
- Own tests: `test_status.py` (36-sentence table), `test_normalize.py`, `test_prompts.py`, `test_pipeline_robustness.py`,
  `test_security.py`, `test_golden_ids.py`.
- Sample outputs for all 5 seeds: `fixtures/findings/*.generated.json` (gitignored; regenerate with the acceptance
  test's sloppy-LLM replay). All 5 are identical to the golden files, IDs included.
- End-to-end with P1B: extraction -> `decide_exemption` gives the expected outcome for all 5 seeds.

## What FINAL needs to know
- **Escape `condition` and `quote` before rendering HTML.** They come from the note (quote) and the LLM (condition).
  `condition` is screened for markup and instructions, but escaping is still FINAL's job.
- `confidence` is the LLM's own estimate. P1B counts current findings only at >= 0.8 and reviews 0.6-0.8.
- `dropped_ungrounded` > 0 is normal. It counts every finding rejected for any safety reason.
- A note missing from `notes_processed` means the LLM failed twice for it; show it as "not read" rather than "no findings".

## Known limits
- Tested with `FakeLLM` only. No live run yet (no working API key); the live smoke test on `N-0002-a` is still to do.
- The status backstop is a cue-word heuristic (6-word window, sentence scope). Unusual phrasing can slip past it;
  it only adds caution, so a miss means the LLM's status is kept.
- `consistency.py` reads `terms` from `config/frailty_rules.json` (P1B's config). If P1B removes or renames terms,
  legitimate findings may be downgraded to uncertain; run `test_security.py` after rule changes.
- Injection detection is pattern-based (`proofkit.common.injection`); the consistency check and P1B's deterministic
  rules are the backstop for wording it misses.

## For the team (outside P1A ownership)
- `pip-audit` flags pypdf 5.1.0 (60 advisories), pytest 8.3.3, python-dotenv 1.0.1, setuptools 84.0.0. Extraction
  uses none of them directly. pyproject also needs `httpx==0.27.2` (anthropic 0.39.0 fails with httpx >= 0.28).
- P1B: change SYN-0001 evidence `F-N-0001-a-0` -> `F-N-0001-a-2` in `fixtures/decisions/expected.json`
  (golden IDs now follow quote order, as the P1A spec requires).

## Role checklist
| Item | Status | Evidence |
|---|---|---|
| CP0: setup, `make check-contracts` green, worktree on `p1a/main` | ✅ | `make check-contracts` 30 passed (live API call ❌: no credits) |
| All spec tests green | ✅ | `test_extraction_spec.py` 12/12 |
| Acceptance golden green for all 5 personas | ✅ | `test_golden_recovered_for_every_member` |
| Injection note SYN-0005 yields only the ankle sprain | ✅ | `test_injected_schizophrenia_never_extracted`; `SYN-0005.generated.json` has 1 finding |
| Prompt reviewed (no untrusted text, few-shot covers all statuses) | ✅ | reviewed by Arsh; `test_prompts.py` |
| Coverage >= 85% for `extraction/` | ✅ | 99% |
| 10+ extra hand-labeled synthetic notes (with P1B) | ❌ | in progress: 52 generated notes + P1B's 10 drafts |
| `/security-check` clean | ✅ | 4 findings fixed test-first (`test_security.py`); bandit clean |
| `/handoff` done, `HANDOFF.md` written | ✅ | this file |
| Extra: status table >= 25 sentences | ✅ | `test_status.py` (36) |
| Extra: duplicate quote, empty response, wrong type, 40k note | ✅ | `test_pipeline_robustness.py` |
| Extra: live smoke test on `N-0002-a` | ❌ | needs a working LLM key |
