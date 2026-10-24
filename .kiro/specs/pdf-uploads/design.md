# Design: pdf-uploads

## Approach
- **Config:** add `"pdf"` back to `upload_limits.allowed_doc_types` in `config/wallet_rules.json`, and update its `why` note. The pyproject pin is bumped to `pypdf==6.21.2` as a team action.
- **PDF checks:** `_checked_text` keeps doing every check before any LLM call. `_pdf_text` gets a hard limit on how much data the PDF may inflate to, so the wallet no longer relies only on pypdf's own decompression limits. Options for GREEN, in order:
  1. Read each page's content stream through a bounded reader. Reject the document if the inflated bytes go over a cap taken from the rules (for example `max_bytes`), or if pypdf reports that it hit a limit or truncated a stream.
  2. If option 1 can't be made reliable with the pypdf 6.21.2 API, run extraction in a subprocess with memory and time limits, as the ponytail note in `_pdf_text` suggests.
  GREEN must first check what pypdf 6.21.2 actually does with the RED bomb. Today it returns without error, and the document goes on to the LLM.
- **Split:** replace `_shares` with an exact apportionment that never goes negative. Pieces are worked out in cents (or hundredths of an hour), using largest-remainder by day weight, so they add up exactly and each piece is ≥ 0. `_records` keeps calling `month_spans`. The text and CSV paths share `_records`, so both are fixed. Remove the stale ponytail comment in `_parse_csv`.

## Error handling
- Every rejection raises `ValueError(f"doc {doc_id}: <reason>")` with no document content. `build_wallet` passes it on, and the whole batch fails.
- If pypdf throws any exception on untrusted bytes, the upload is rejected ("unreadable pdf").
- If a split piece would break the contract, the statement should not vanish silently. Open question for the human: a statement whose hours go over 744 in one month (more than 24 hours a day) is impossible. Should it be rejected and flagged for review, or should the split rebalance it? The RED property allows hours up to 2000.00 on periods as short as 32 days and expects them all to be kept.

## Security notes
- The decompression-bomb test builds the bomb in memory and never writes it to disk.
- PDF text is untrusted. It goes only through `untrusted_text=` and gets the same grounding, injection and date checks as text documents.
- `filename` is never used as a path (`test_no_wallet_code_touches_filename`).
- Size checks happen before decoding, and inflation is limited during decoding.
- Supply chain: the pin bump is tracked by the existing version-gated test, and pip-audit should show no pypdf advisories after the bump.

## Correctness properties
| Property | Checks | Test |
|---|---|---|
| P1 Config gate: shipped rules allow pdf | R1.1 | `test_shipped_rules_allow_pdf_uploads` |
| P2 Version gate: pdf stays off on old pypdf | R1.2 | `test_pdf_uploads_off_while_pinned_pypdf_has_known_cves` |
| P3 Format parity: PDF and text give the same month | R2.1, R2.2 | `test_pdf_version_of_uber_fixture_gives_same_month_as_text` |
| P4 Bomb rejection: ValueError naming doc_id, no LLM call | R3.1, R3.2, R3.4 | `test_decompression_bomb_pdf_is_rejected` |
| P5 Limits kept for PDFs | R3.3 | `test_bad_uploads_rejected`, `test_size_limit_applies_to_valid_content` |
| P6 Month containment | R4.1 | `test_every_piece_lies_inside_one_calendar_month` |
| P7 Contiguous coverage | R4.2 | `test_pieces_are_contiguous_and_cover_the_whole_period` |
| P8 Exact conservation, nothing dropped | R4.3, R4.5 | `test_pieces_sum_exactly_to_source_income_and_hours` |
| P9 Quote preservation | R4.4 | `test_every_piece_keeps_the_source_quote` |
| P10 CSV split | R4.6 | `test_csv_row_longer_than_31_days_is_split_by_month` (a CSV property test is still to do) |

Known counterexamples from RED:
- $0.02 over 2027-01-01 to 2027-04-01 gives a last piece of −0.01, so the statement is dropped.
- 768.01 hours over 2027-01-01 to 2027-02-01 gives 744.01 hours in January, so the statement is dropped.
