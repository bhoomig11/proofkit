# Tasks: pdf-uploads

- [x] 1. RED: config gate test `test_shipped_rules_allow_pdf_uploads` (R1.1)
- [x] 2. RED: PDF fixture script `tests/unit/wallet/make_pdf_fixture.py`, which writes `fixtures/wallet/D-0002-ridenow-feb-pdf.json`
- [x] 3. RED: parity test `test_pdf_version_of_ridenow_fixture_gives_same_month_as_text` (R2)
- [x] 4. RED: in-memory decompression-bomb test `test_decompression_bomb_pdf_is_rejected` (R3.1, R3.2, R3.4)
- [x] 5. RED: Hypothesis split properties in `test_split_properties.py` (R4.1 to R4.5)
- [ ] 6. RED: CSV version of the split properties (R4.6)
- [ ] 7. Human decision: how to handle more than 744 hours in one month (see the design's open question). Do not change the property test without approval.
- [ ] 8. GREEN: team bumps `pypdf==6.21.2` in `pyproject.toml`
- [ ] 9. GREEN: add `"pdf"` to `allowed_doc_types` in `config/wallet_rules.json` and update the `why` note (tasks 1 and 3)
- [ ] 10. GREEN: limit inflation in `_pdf_text`, rejecting with a message that names the doc_id; fall back to subprocess extraction with memory and time limits (task 4)
- [ ] 11. GREEN: exact, non-negative apportionment in `_shares`/`_records` (task 5)
- [ ] 12. REFACTOR: remove the stale ponytail comment in `_parse_csv`, update HANDOFF.md (PDF on, split guarantees), run `make test-p2`, coverage ≥ 85%, ruff, `make check-ownership`, pip-audit
