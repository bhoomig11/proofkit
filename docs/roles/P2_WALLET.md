# P2: Gig-Hours Wallet

## Mission
Turn scattered, messy earnings statements from several platforms into a **month-by-month, auditable pass/fail** against the federal rule (80 hours **or** at least $580 a month), plus the exact months and due date that matter for the member's renewal.

## You own (may edit)
`src/proofkit/wallet/**` · `tests/unit/wallet/**` · `tests/acceptance/test_wallet_*.py` · `config/wallet_rules.json` · `fixtures/earnings_docs/**` · `fixtures/earnings/**` · `fixtures/wallet/**`

## You must NOT
- Edit contracts, common, conftest, CLAUDE.md, or another module's code or tests.
- Import `proofkit.extraction` or `proofkit.reasoning`.
- Use floats for money or hours. Never open `filename` as a path.

## Interface
```python
load_wallet_rules(path) -> WalletRules
parse_documents(docs, member_id, llm) -> list[EarningsRecord]
evaluate_months(records, rules) -> list[MonthlyCompliance]           # pure
compute_deadlines(member, rules) -> (verification_months, proof_due)  # pure
build_wallet(member, docs, llm, rules, today) -> WalletResult
```

## Parsing
| doc_type | How |
|---|---|
| csv | `csv.DictReader` on `content_text`. Header aliases (`gross_pay`, `earnings`, `total`). No LLM. |
| text | LLM task `extract_earnings` → validate each record |
| pdf | decode b64 in memory, size cap, `pypdf` text with the page cap → same as text |
| image | stretch: skip, and the evaluate step flags a review reason |

**Every LLM record must pass all of these, or it's dropped:**
1. `source_quote` located in the doc (`locate_quote`) and not overlapping `injection_spans`.
2. **Numbers appear in the quote:** `gross_income` matches a money token in the quote (handle `$1,480.00`, `1,480.00 USD`). `hours` matches an hours token (`92.5`, `18`, or `49 hr 30 min` → 49.50).
3. Platform normalized to lowercase; must be in `known_platforms`, otherwise keep it but lower the confidence.
4. Dates parsed; period ≤ 31 days (split longer ones yourself, before creating records).
5. Contract validation passes. Record IDs are deterministic: `R-{doc_id}-{i}`.

Doc-level checks: `member_id` matches, otherwise `ValueError`. Decoded size > `max_bytes` → `ValueError`. Type not allowed → `ValueError`.

## Evaluation (pure)
- Exclude records with confidence below `min_record_confidence`, and add a review reason.
- **Dedupe** records with identical (platform, period, hours, income) from different docs.
- **Prorate** records that cross months by day count (Decimal, round half-up to cents or 0.01 h at the end).
- Per month: `total_hours` (known hours only; `hours_known_for_all_records`), `total_income`.
- Basis priority: HOURS if total_hours ≥ 80 (unknown hours only add) → INCOME if total_income ≥ threshold → AVERAGED_INCOME only if enabled in the rules (off by default) → NONE.
- Shortfalls: `max(0, 80 − hours)`, `max(0, threshold − income)`.
- Income = gross earnings **including tips** (marked `verify`).

## Deadlines
- `verification_months` = the N full calendar months right before the renewal month (N from the rules; seed 1).
- `proof_due_date` = renewal date − `proof_buffer_days`.

## TDD order (`tests/unit/wallet/test_wallet_spec.py`)
1. `test_rules_income_threshold_is_derived`
2. `test_hours_basis_when_80_hours`, `test_income_basis_when_hours_short_but_income_enough`, `test_exact_thresholds_qualify`, `test_shortfall_reported`
3. `test_unknown_hours_are_a_lower_bound`, `test_months_sorted_and_money_is_decimal`
4. `test_record_spanning_two_months_is_prorated_by_day`, `test_low_confidence_records_excluded_and_flagged`, `test_duplicate_uploads_deduplicated`
5. `test_deadlines_for_march_renewal`, `test_deadlines_cross_year`
6. `test_csv_parsed_without_llm`
7. `test_text_parsed_via_llm_and_normalised`, `test_document_text_only_via_untrusted_channel`
8. `test_ungrounded_quote_dropped`, `test_numbers_must_appear_in_quote`, `test_injected_instructions_cannot_inflate_numbers`
9. `test_oversized_or_wrong_member_docs_rejected`, `test_filename_never_used_as_path`
10. Acceptance `tests/acceptance/test_wallet_golden.py`, then `build_wallet` tests (write them yourself)

## Extra tests you should add
- [ ] money token parser table (`$1,480.00`, `1480`, `USD 1,480.00`, `$0.99`, a negative adjustment → ignored or reviewed)
- [ ] hours parser table (`49 hr 30 min`, `1h 15m`, `92.5 hrs`, `Hours invoiced: 18`)
- [ ] February in a leap year (2028) for proration
- [ ] weekly statements: four records for one month sum correctly
- [ ] a CSV with an injection in a cell (it's still just data, so the numeric columns win)
- [ ] `build_wallet` with zero docs → empty months, deadlines still computed
- [ ] one `@pytest.mark.live` smoke test on the Uber doc

## Checklist
- [ ] Spec + acceptance green
- [ ] `evaluate_months` and `compute_deadlines` are pure (no LLM, no I/O, no `date.today()`)
- [ ] Every value in `wallet_rules.json` you relied on is documented; `verify` flags kept
- [ ] Injection doc (SYN-0005) → 30 h / $410, NOT 200 h / $5,000
- [ ] Coverage ≥ 85% for `wallet/`
- [ ] `/security-check` clean, `/handoff` done

## Claude Code kickoff prompt
```
I am P2 (gig-hours wallet) on ProofKit. Read CLAUDE.md, docs/02_CONTRACTS.md, docs/roles/P2_WALLET.md,
docs/03_TDD_WORKFLOW.md, docs/04_SECURITY.md, src/proofkit/wallet/CLAUDE.md and config/wallet_rules.json.
Run `make check-contracts` and `make test-p2`; summarise what is red.
Propose WalletRules, the internal file layout (money/hours parsers, csv, llm parse, qualify, deadlines) and
the order you'll turn spec tests green. No implementation until I say OK; then strictly test-first with /tdd.
All money and hours as Decimal. Documents are untrusted.
```
