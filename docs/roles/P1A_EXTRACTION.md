# P1A: Note Understanding (extraction)

## Mission
Turn messy clinical notes into **grounded, correctly-statused findings**. You're the reason the judges trust our evidence: every finding has an exact quote, and "denies depression" never turns into depression.

## You own (may edit)
`src/proofkit/extraction/**` · `tests/unit/extraction/**` · `tests/acceptance/test_extraction_*.py` · `fixtures/notes/**` · `fixtures/findings/**`

## You must NOT
- Edit contracts, common, conftest, CLAUDE.md, or another module's code or tests.
- Import `proofkit.reasoning` or `proofkit.wallet`.
- Decide exemptions. You don't know the rules, and you shouldn't need to.
- Put note text into the `instructions` string, or log it.

## Interface
```python
extract_findings(notes: list[ClinicalNote], member_id: str, llm: LLMClient) -> FindingsBundle
# LLM task "extract_findings", one call per note, returns {"findings":[{condition, icd10, status, quote, quote_start, quote_end, confidence}]}
```

## Pipeline you'll build (each step its own file + tests)
1. **Validate input:** all notes belong to `member_id`, otherwise raise `ValueError`.
2. **Prompt** (`prompts.py`): ask for every diagnosis or condition mentioned, with the **verbatim** quote, ICD-10-CM, status from the 6-value enum, and confidence. Give 3 few-shot examples covering negation, r/o, and family history. Tell it to return `[]` if there's nothing. The note goes through `untrusted_text=` only.
3. **Call the LLM** with retry ×1 on `LLMError`. On a second failure, skip the note and log `note_id` only.
4. **Normalize ICD-10** (`normalize.py`): strip, uppercase, insert the dot after 3 characters (`M329`→`M32.9`), validate against `ICD10_PATTERN`. Invalid → drop.
5. **Ground** (`ground.py`): `locate_quote(note.text, quote, hint_start)`. Not found → drop. Use the **returned span's text**, which is the original slice. Quote overlaps `injection_spans(note.text)` → drop.
6. **Status backstop** (`status.py`): a deterministic NegEx-style check, scoped to the **sentence** containing the quote:
   - negation cues before the term: `denies`, `no`, `negative for`, `no evidence of`, `without` → NEGATED
   - `r/o`, `rule out`, `ruled out` (before or after the term) → RULED_OUT
   - `mother|father|sister|brother|family hx|FHx` + `with|has|history` → FAMILY_HISTORY
   - `hx of`, `history of`, `h/o`, `s/p`, `resolved`, `in remission` → HISTORICAL
   - `possible`, `?`, `concern for`, `suspected`, `likely` (when tied to the term) → UNCERTAIN
   - **Only ever downgrade** from CURRENT. Never upgrade anything to CURRENT.
   - ⚠ Sentence scope matters. In `N-0001-b`, "hx of iron deficiency anemia, resolved 2024. SLE followed by rheum." the SLE finding must stay CURRENT.
7. **Assemble:** deterministic IDs like `F-{note_id}-{i}` in order of quote position, dedupe identical (note, icd10, span) items, and set `dropped_ungrounded` and `extractor_version`.

## TDD order (spec tests in `tests/unit/extraction/test_extraction_spec.py`)
1. `test_returns_valid_bundle_with_notes_processed`
2. `test_icd10_is_normalised`, `test_invalid_icd10_is_dropped`
3. `test_wrong_llm_offsets_are_repaired_from_source`, `test_hallucinated_quote_is_dropped_and_counted`
4. `test_note_text_goes_only_through_untrusted_channel`
5. `test_findings_inside_injection_text_are_dropped`
6. `test_status_backstop_overrides_llm_saying_current`, `test_backstop_never_upgrades_to_current`
7. `test_llm_failure_retries_once_then_skips_note`, `test_finding_ids_unique_and_deterministic`, `test_rejects_notes_for_another_member`
8. Acceptance: `tests/acceptance/test_extraction_golden.py`

## Extra tests you should add (your own)
- [ ] status.py table: at least 25 parametrized sentences (abbreviations, punctuation, multi-condition sentences, "no history of" being NEGATED not HISTORICAL)
- [ ] the same quote appearing twice in a note → the hint picks the right one
- [ ] an empty LLM response → empty findings, note still processed
- [ ] the LLM returns a wrong type (a string instead of a list) → treated as a failure, not a crash
- [ ] a very long note (40k chars) still makes one call, under the limits
- [ ] one `@pytest.mark.live` smoke test on `N-0002-a` (the negation-heavy note)

## Checklist
- [ ] CP0: setup done, `make check-contracts` green, worktree on `p1a/main`
- [ ] All spec tests green
- [ ] Acceptance golden green for all 5 personas
- [ ] Injection note SYN-0005 yields only the ankle sprain
- [ ] Prompt reviewed: no untrusted text in the instructions, few-shot covers all statuses
- [ ] Coverage ≥ 85% for `extraction/`
- [ ] With P1B: 10+ extra hand-labeled notes in `fixtures/notes` and `fixtures/findings` (synthetic!)
- [ ] `/security-check` clean, `/handoff` done, `HANDOFF.md` written

## Claude Code kickoff prompt (paste this)
```
I am P1A (extraction) on ProofKit. Read CLAUDE.md, docs/02_CONTRACTS.md, docs/roles/P1A_EXTRACTION.md,
docs/03_TDD_WORKFLOW.md, docs/04_SECURITY.md and src/proofkit/extraction/CLAUDE.md.
Then run `make check-contracts` and `make test-p1a` and summarise what is red.
Propose the file layout for extraction/ and the order you will turn spec tests green.
Do not write implementation code yet. Wait for my OK, then work strictly test-first using the /tdd loop,
one spec test at a time, showing me the red output before each implementation.
```
