# Offline demo mode: tasks

Branch `final/karthik-demo`. Each task: RED (run only that test and show it failing with NotImplementedError or an
assertion), GREEN (minimum code), then `mingw32-make test-final PY=.venv/Scripts/python.exe`.
All tests live in `tests/integration/test_demo_mode.py`.

- [ ] 0. Scaffold so tests fail for the right reason, not an ImportError
  - Create `src/proofkit/integration/demo.py` with `demo_llm` and `choose_llm` raising `NotImplementedError`, plus
    docstrings. Export `demo_llm`, `choose_llm`, `MODE_LABELS` and `DEMO_SUMMARY` from `integration/__init__.py`.
  - Commit `test:` together with task 1's test.

- [ ] 1. test: `test_demo_findings_match_golden_for_every_persona` (Req 1.1, 1.2)
  - feat: fixture loader, `note_by_text` and `note_items` tables, the exact-text findings responder.
- [ ] 2. test: `test_demo_unmatched_note_returns_no_findings` and `test_demo_unknown_task_raises_llm_error` (Req 1.3)
  - feat: empty result for unmatched text (unknown task already handled by FakeLLM).
- [ ] 3. test: `test_demo_records_match_golden` and `test_demo_wallet_months_match_expected` (Req 2.1, 2.2)
  - Includes SYN-0003 `months == []`, SYN-0004 $60.00 short, and `verification_months` / `proof_due_date`.
  - feat: document text decoding, `doc_by_text` and `doc_items`, the earnings responder with the merge by
    (`source_doc_id`, `source_quote`).
- [ ] 4. test: `test_demo_unmatched_document_returns_no_records` (Req 2.3)
- [ ] 5. test: `test_demo_statement_for_exempt_personas` (Req 3)
  - The EXEMPT IDs match `expected_decisions`. The statement contains `DEMO_SUMMARY`. No `draft_statement` call for
    NOT_EXEMPT personas.
  - feat: `DEMO_SUMMARY` and the statement responder.
- [ ] 6. test: `test_demo_untrusted_text_only_in_user_block` (Req 7.4)
  - For every call in `llm.calls`: `"<untrusted_document>"` in `user`, and the source text not in `instructions`.
- [ ] 7. test: `test_demo_syn0005_injection_has_no_effect` (Req 7.2)
- [ ] 8. test: `test_demo_appended_injection_changes_nothing` (Req 7.3)
  - feat: the containment fallback with the (most items, id) tie-break.
- [ ] 9. test: `test_choose_llm_mode_table` (parametrized), `test_choose_llm_live_without_key_raises` and
  `test_choose_llm_explicit_arg_beats_env` (Req 4.1-4.5)
  - Monkeypatch `proofkit.integration.demo.load_settings` (fake `Settings`, a non-key-looking string) and
    `proofkit.integration.demo.AnthropicClient` (a stub). Use `monkeypatch.setenv` / `delenv` for `PROOFKIT_DEMO`.
  - feat: `choose_llm` per the decision table.
- [ ] 10. test: `test_mode_labels` (Req 4.6)
  - feat: `MODE_LABELS`.
- [ ] 11. test: `test_demo_mode_opens_no_socket` and `test_demo_mode_never_builds_anthropic_client` (Req 5)
  - Patch `socket.socket`, `socket.create_connection` and `socket.getaddrinfo` to count and raise. Run all personas
    and `choose_llm(demo=True)`.
- [ ] 12. test: `test_demo_is_deterministic_across_runs` (Req 6.1, 6.2)
- [ ] 13. test: `test_demo_invalid_fixture_names_file_only` and `test_demo_missing_fixture_dir_raises` (Req 8.1, 8.2)
  - Use `tmp_path` copies of the fixtures with one corrupted golden file.
- [ ] 14. test: `test_choose_llm_never_logs_key_or_text` (Req 8.3, 8.4), with `caplog` at DEBUG.
- [ ] 15. Property tests (design P1-P4)
  - `test_prop_deterministic_for_any_persona_order` (P1)
  - `test_prop_no_socket_for_any_persona_subset` (P2)
  - `test_prop_replay_equals_golden_for_any_input_order` (P3)
  - `test_prop_appended_text_is_inert` (P4)
- [ ] 16. Refactor with everything green
  - `mingw32-make test-final`, `check-contracts` and `check-ownership`;
    `.venv/Scripts/python -m ruff check src tests scripts`; `.venv/Scripts/python -m bandit -q -r src`;
    `.venv/Scripts/pip-audit`; `scripts/scan_secrets.py` clean. Commit with `refactor:`.
- [ ] 17. Docs: add an offline demo section to `src/proofkit/integration/HANDOFF.md` covering `PROOFKIT_DEMO=1`,
  `choose_llm`, the label, and what is replayed. Verified by `test_mode_labels` staying green.
- [ ] 18. App: once `app/` has pages, show `MODE_LABELS[mode]` with `st.caption` next to the disclaimer on every page
  (no `unsafe_allow_html`). Verified by `test_mode_labels`. Owner of the app code: P1A.
- [ ] 19. After P1B merges `final/status-rules`: test `test_run_member_offline_matches_expected_status`
  - `run_member(..., demo_llm(), ...)` for all 5 personas matches `expected_status.json`, with no network.
  - Write this only after the merge, so the branch never carries a red test.
