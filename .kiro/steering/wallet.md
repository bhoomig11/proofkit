---
inclusion: fileMatch
fileMatchPattern: "{src/proofkit/wallet/**,tests/unit/wallet/**,tests/acceptance/test_wallet_*,config/wallet_rules.json}"
---
# Wallet (P2) rules (src/proofkit/wallet/CLAUDE.md, HANDOFF.md)

## Scope
- Edit only on `p2/` branches, and only within the p2/ paths in structure.md.
- Never import `proofkit.extraction` or `proofkit.reasoning`.
- After every change run `make test-p2` (Windows: `mingw32-make test-p2 PY=.venv/Scripts/python.exe`).

## Numbers and rules
- Money and hours are `Decimal`. Round half-up to 2 places, and only at the end. No floats anywhere.
- Load rules only through `load_wallet_rules(path)`. Keep every `"verify": true` flag.
- `monthly_income_required` must equal `federal_minimum_wage` x `monthly_hours_required` (7.25 x 80 = 580.00); the loader rejects anything else.
- `allow_seasonal_income_averaging: true` is rejected until averaging is implemented. Keep that rejection.

## Documents are untrusted
- Check every document before any LLM call: `member_id` matches, the type is in `allowed_doc_types`, decoded size <= `max_bytes`, valid base64/UTF-8, PDF page cap. Otherwise raise `ValueError` naming the `doc_id` only, never the contents.
- `filename` is display-only and never opened as a path. Parse in memory.
- CSV: use `csv.DictReader` with no LLM. Drop bad rows, never guess. `source_quote` is the exact CSV line.
- Text: use LLM task `extract_earnings` with the document passed only via `untrusted_text=`. Keep a record only if all of these hold:
  - `locate_quote` finds the quote and it doesn't overlap `injection_spans`;
  - `gross_income` matches a money token and `hours` matches an hours token in the quote;
  - the stored quote is the document's own text (max 500 chars) and the dates parse.
- Period dates that aren't written in the document drop the record below the confidence threshold and flag the month.
- Periods are at most 31 days. Split longer statements into calendar-month records, prorated by day, that sum to the source total to the cent and share its `source_quote`.
- Platforms are lowercase `[a-z0-9_]`, mapped to `known_platforms` by whole-word longest prefix. Unknown platforms get confidence 0.5.
- Record IDs are `R-{doc_id}-{i}`.
- PDF stays out of `allowed_doc_types` until the team bumps `pypdf` from 5.1.0 to 6.21.2 on main. Keep `test_pdf_uploads_off_while_pinned_pypdf_has_known_cves`.
- Images yield no records and flag every verification month `needs_review`.

## evaluate_months and compute_deadlines are pure
- No LLM, I/O or clock. `tests/unit/wallet/test_purity.py` must stay green. `build_wallet` accepts `today` but doesn't use it.
- Exclude records below `min_record_confidence` (0.7), unknown platforms, and overlapping same-platform statements. Name each one in `review_reasons`.
- Dedupe identical (platform, period, hours, income) records from different documents.
- Prorate by day, including leap years. `total_hours` counts known hours only, so unknown hours make it a lower bound.
- Basis order: HOURS (>= 80) -> INCOME (>= threshold) -> AVERAGED_INCOME (only if enabled; off) -> NONE. `qualifies` holds exactly when `basis != none`.
- Shortfalls are `max(0, 80 - hours)` and `max(0, threshold - income)`. Income is gross including tips (`verify`). Months are sorted.
- `verification_months` = the N full calendar months right before the renewal month. `proof_due_date` = renewal date - `proof_buffer_days` (14).

## Regression anchors
- SYN-0005: 30 h / $410, never 200 h / $5,000 (`test_injected_statement_gives_30_hours_and_410_dollars`).
- SYN-0004: $520 in Feb 2027, $60 short, proof due 2027-03-06.
- Coverage stays >= 85% (currently 97%). Update `HANDOFF.md` whenever the behavior changes.
