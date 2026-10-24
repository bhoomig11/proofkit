# P2 wallet: handoff

Turns earnings documents into a month-by-month pass/fail against 80 hours or $580, plus the verification months and proof due date for a member's renewal.

## How to call it

```python
from proofkit.wallet import build_wallet, load_wallet_rules

rules = load_wallet_rules(Path("config/wallet_rules.json"))
wallet = build_wallet(member, docs, llm, rules, today)   # Member, list[EarningsDocument] -> WalletResult
```

`build_wallet` raises `ValueError` if any document belongs to another member, has a disallowed type, is over `max_bytes`, is not valid base64 or UTF-8, or is an unreadable PDF or one over the page cap. Every document is checked before any LLM call, so a bad upload fails the whole batch with no partial result. Catch it and show the member which upload was rejected (the message names the `doc_id`, never the contents).

The lower-level functions are public too: `parse_documents(docs, member_id, llm, *, rules=None)`, `evaluate_months(records, rules)`, `compute_deadlines(member, rules)`. `parse_documents` gained an optional keyword `rules`; without it, it loads `config/wallet_rules.json`.

## What works

- CSV is parsed without the LLM. Bad rows are dropped, never guessed. The `source_quote` is the exact CSV line.
- Text goes through the LLM (`extract_earnings`) on the `untrusted_text` channel only. A record is kept only if its quote is found in the document, doesn't touch an injection line, and contains the claimed income and hours. The stored quote is the document's own text.
- If the LLM's period dates aren't written in the document, the record drops below the confidence threshold: it stays in `records` but doesn't count, and its month is flagged for review.
- `evaluate_months` and `compute_deadlines` are pure (no LLM, I/O or clock; `tests/unit/wallet/test_purity.py`). Proration is by day (leap years included). Records below 0.7 confidence, unknown platforms, and same-platform statements from different documents with overlapping periods are excluded and named in `review_reasons`. Identical statements uploaded twice are deduped.
- SYN-0005's injected "200 hours and $5,000" ends at 30 h / $410 (`tests/acceptance/test_wallet_golden.py::test_injected_statement_gives_30_hours_and_410_dollars`).

## What FINAL needs to know

- A member with no documents gets `months == []`. The status rule must require each verification month to be **present** and qualifying, or "all verification months qualify" is vacuously true.
- `needs_review` months come from low confidence, unknown platforms, overlapping statements, unverified dates, or unread images. Route them to NEEDS_REVIEW, not AT_RISK.
- An image upload yields no records and flags every verification month for review, creating an empty month entry if needed.
- `today` is accepted but unused.
- Escape `source_quote` and `platform` before rendering. Platforms are already restricted to `[a-z0-9_]`, but quotes are raw document text.

## Known limits

- **PDF uploads are off** in `config/wallet_rules.json`. The pinned `pypdf==5.1.0` has 60 known advisories (pip-audit), including decompression bombs; 6.21.2 fixes them. After the team bumps the pin, add `"pdf"` back to `allowed_doc_types`. The PDF path is written and tested; `test_pdf_uploads_off_while_pinned_pypdf_has_known_cves` stops failing once the pin is bumped.
- A CSV row covering more than 31 days is dropped, not split by month.
- Inside a grounded quote, the LLM may pick any written amount (for example a year-to-date figure instead of the month). The quote is capped at 500 characters and must be in the document, which bounds this.
- Two overlapping same-platform statements inside one document both count (only cross-document overlaps are caught).
- Seasonal income averaging is off and not implemented.
- The live smoke test (`tests/acceptance/test_wallet_live.py`) is written but hasn't been run against the real API yet.

## Rules this module relies on (`config/wallet_rules.json`)

| Key | Value | Verify | Used for |
|---|---|---|---|
| `monthly_hours_required` | 80 | no (statute) | HOURS basis, hours shortfall |
| `federal_minimum_wage` | 7.25 | yes | derives the income threshold |
| `monthly_income_required` | 580.00 | yes | INCOME basis; loader rejects it unless it equals wage × hours |
| `allow_seasonal_income_averaging` | false | yes | off until checked against the CMS rule |
| `verification_months_before_renewal` | 1 | yes | how many months before renewal are checked |
| `proof_buffer_days` | 14 | no (product choice) | proof due date = renewal − 14 days |
| `min_record_confidence` | 0.7 | not flagged | records below it are excluded and flagged |
| `known_platforms` | 11 names | not flagged | unknown platforms get confidence 0.5 |
| `upload_limits` | 10 MB, text/csv/image, 20 pages | not flagged | upload rejection |
| `requirements_start_date` | 2027-01-01 | no | not used yet |

## Checklist (`docs/roles/P2_WALLET.md`)

- ✅ Spec + acceptance green: `make test-p2`, 133 passed
- ✅ `evaluate_months` / `compute_deadlines` pure: `tests/unit/wallet/test_purity.py`
- ✅ `wallet_rules.json` values documented (table above), `verify` flags kept
- ✅ SYN-0005 → 30 h / $410: `test_injected_statement_gives_30_hours_and_410_dollars`
- ✅ Coverage ≥ 85%: 97%
- ✅ `/security-check`: two MEDIUM findings fixed test-first; the pypdf HIGH is mitigated by turning PDF off and needs a team pin bump
- ✅ `/handoff`: this file
- ✅ Extras: token tables (`test_tokens.py`), leap year and dedupe (`test_qualify.py`), weekly sum, zero docs, images (`test_wallet.py`), CSV injection cell (`test_parse.py`), live smoke test (written, not run)
