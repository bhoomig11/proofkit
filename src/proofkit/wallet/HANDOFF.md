# P2 wallet: handoff

Turns earnings documents into a month-by-month pass/fail against 80 hours or $580, plus the verification months and proof due date for a member's renewal.

## How to call it

```python
from proofkit.wallet import build_wallet, load_wallet_rules

rules = load_wallet_rules(Path("config/wallet_rules.json"))
wallet = build_wallet(member, docs, llm, rules, today)   # Member, list[EarningsDocument] -> WalletResult
```

`build_wallet` raises `ValueError` if any document belongs to another member, has a disallowed type, is over `max_bytes`, is not valid base64 or UTF-8, or is a PDF that is unreadable, over the page cap, or has a stream that inflates past `max_bytes`. Every document is checked before any LLM call, so a bad upload fails the whole batch with no partial result. Catch it and show the member which upload was rejected (the message names the `doc_id`, never the contents).

The lower-level functions are public too: `parse_documents(docs, member_id, llm, *, rules=None)`, `evaluate_months(records, rules)`, `compute_deadlines(member, rules)`. `parse_documents` gained an optional keyword `rules`; without it, it loads `config/wallet_rules.json`.

## What works

- CSV is parsed without the LLM. Bad rows are dropped, never guessed. The `source_quote` is the exact CSV line.
- Text goes through the LLM (`extract_earnings`) on the `untrusted_text` channel only. A record is kept only if its quote is found in the document, doesn't touch an injection line, and contains the claimed income and hours. The stored quote is the document's own text.
- If the LLM's period dates aren't written in the document, the record drops below the confidence threshold: it stays in `records` but doesn't count, and its month is flagged for review.
- `evaluate_months` and `compute_deadlines` are pure (no LLM, I/O or clock; `tests/unit/wallet/test_purity.py`). Proration is by day (leap years included). Records below 0.7 confidence, unknown platforms, and same-platform statements with overlapping periods (from different documents, or a monthly total next to a weekly line in one document) are excluded and named in `review_reasons`. Identical statements uploaded twice are deduped.
- PDF uploads are on (`pypdf==6.21.2`, pip-audit clean). Text is extracted in memory, then goes through the same LLM, grounding, injection and date checks as text. A one-page PDF of the SYN-0002 Uber statement gives the same month as the text version (`test_pdf_uploads.py`).
- Decompression bombs are rejected: `_pdf_text` runs pypdf under `apply_configuration` with every decoder output limit set to `max_bytes` (10 MiB), and pypdf's zlib decoder uses `max_length`, so no stream is ever inflated past that. Each page's contents are decoded before text extraction so the `LimitReachedError` surfaces as `ValueError("doc <id>: pdf stream inflates past ... bytes")`, with no LLM call. Test: a 200 MiB-of-zeros stream built in memory.
- A statement covering more than 31 days is split into calendar-month records, prorated by day with the largest-remainder method in whole cents (and hundredths of an hour): every piece is >= 0, the pieces add up exactly to the source total, and all share its `source_quote`. Text and CSV share this path.
- A statement claiming more than 24 hours a day (hours > 24 × its days) is never dropped or capped: it is kept with `hours=None` and confidence 0.5, so `evaluate_months` excludes it and flags every month it touches for review.
- Hypothesis property tests (`test_split_properties.py`, 200 examples each) check the split: never dropped, one calendar month per piece, contiguous full coverage, quote kept, income and hours exact, and the over-24-hours rule. They found two bugs, both fixed: (1) rounding early pieces up left a negative last piece ($0.02 over 2027-01-01..04-01 gave −$0.01), so the contract dropped the whole statement; (2) 768.01 h over 2027-01-01..02-01 put 744.01 h in January, over the contract's 744 cap, so it was dropped too.
- Platform names like "DoorDash Dasher" or "Uber Eats" map to the known platform (whole-word prefix, longest match).
- SYN-0005's injected "200 hours and $5,000" ends at 30 h / $410 (`tests/acceptance/test_wallet_golden.py::test_injected_statement_gives_30_hours_and_410_dollars`).

## What FINAL needs to know

- A member with no documents gets `months == []`. The status rule must require each verification month to be **present** and qualifying, or "all verification months qualify" is vacuously true.
- `needs_review` months come from low confidence, unknown platforms, overlapping statements, unverified dates, or unread images. Route them to NEEDS_REVIEW, not AT_RISK.
- An image upload yields no records and flags every verification month for review, creating an empty month entry if needed.
- `today` is accepted but unused.
- Escape `source_quote` and `platform` before rendering. Platforms are already restricted to `[a-z0-9_]`, but quotes are raw document text.

## Known limits

- PDFs are text-only: scanned PDFs yield no text, so the LLM finds no records. `test_pdf_uploads_off_while_pinned_pypdf_has_known_cves` still guards against a pypdf downgrade below 6.21.2.
- The CSV path has no property tests yet (spec task 6); it shares `_records` with text, and `test_csv_row_longer_than_31_days_is_split_by_month` covers it by example.
- Inside a grounded quote, the LLM may pick any written amount (for example a year-to-date figure instead of the month). The quote is capped at 500 characters and must be in the document, which bounds this.
- Seasonal income averaging is not implemented. The rules loader rejects `allow_seasonal_income_averaging: true`, so it can't be switched on and silently ignored.
- `requirements_start_date` is loaded but not used by P2: the wallet reports months as they are. If FINAL needs to treat months before 2027-01 as not yet required, read it from `WalletRules`.
- Live tests (`tests/acceptance/test_wallet_live.py`) passed 3/3 twice in a row on Groq `openai/gpt-oss-120b` (Uber doc, SYN-0005 injection, every persona's pass/fail). They have not been run on Anthropic. Groq's free tier allows 8k tokens a minute, so the test adapter waits out 429s and a run takes about 35 s.

## Rules this module relies on (`config/wallet_rules.json`)

| Key | Value | Verify | Used for |
|---|---|---|---|
| `monthly_hours_required` | 80 | no (statute) | HOURS basis, hours shortfall |
| `federal_minimum_wage` | 7.25 | yes | derives the income threshold |
| `monthly_income_required` | 580.00 | yes | INCOME basis; loader rejects it unless it equals wage × hours |
| `allow_seasonal_income_averaging` | false | yes | loader rejects true until averaging is implemented |
| `verification_months_before_renewal` | 1 | yes | how many months before renewal are checked |
| `proof_buffer_days` | 14 | no (product choice) | proof due date = renewal − 14 days |
| `min_record_confidence` | 0.7 | not flagged | records below it are excluded and flagged |
| `known_platforms` | 11 names | not flagged | unknown platforms get confidence 0.5 |
| `upload_limits` | 10 MB, text/csv/image/pdf, 20 pages | not flagged | upload rejection; `max_bytes` also caps each decoded PDF stream |
| `requirements_start_date` | 2027-01-01 | no | loaded, not used by P2 (see known limits) |

## Checklist (`docs/roles/P2_WALLET.md`)

- ✅ Spec + acceptance green: `tests/unit/wallet` + `tests/acceptance/test_wallet_golden.py`, 156 passed (was 133; now includes 3 in `test_pdf_uploads.py` and 10 in `test_split_properties.py`)
- ✅ `evaluate_months` / `compute_deadlines` pure: `tests/unit/wallet/test_purity.py`
- ✅ `wallet_rules.json` values documented (table above), `verify` flags kept
- ✅ SYN-0005 → 30 h / $410: `test_injected_statement_gives_30_hours_and_410_dollars`
- ✅ Coverage ≥ 85%: 97%
- ✅ `/security-check`: two MEDIUM findings fixed test-first; the pypdf HIGH is fixed by the 6.21.2 bump plus the per-stream inflate cap
- ✅ `/handoff`: this file
- ✅ Extras: token tables (`test_tokens.py`), leap year and dedupe (`test_qualify.py`), weekly sum, zero docs, images (`test_wallet.py`), CSV injection cell (`test_parse.py`), live tests on Groq (3/3, twice)

## Team actions (outside P2's paths)

- Done: `pypdf==6.21.2` and `hypothesis==6.170.9` are pinned in `pyproject.toml`.
- pip-audit also flags `pip`, `pytest` and `python-dotenv` pins.
- `make security` calls `bandit` and `pip-audit` from the system PATH and ignores failures, so it silently skips them unless the venv is active. Use `.venv/bin/bandit` / `.venv/bin/pip-audit` or `$(PY) -m` in the Makefile.
