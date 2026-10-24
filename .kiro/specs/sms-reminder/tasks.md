# Tasks: sms-reminder

- [x] 1. RED: example tests in tests/integration/test_reminder.py (5 personas, Dev specifics, due date, month selection, greeting table, invariance, purity)
- [x] 2. RED: Hypothesis properties in tests/integration/test_reminder_properties.py (R1-R7, 300 examples)
- [x] 3. Confirm RED is ModuleNotFoundError for proofkit.integration.reminder
- [ ] 4. GREEN: create src/proofkit/integration/reminder.py with `_first_name`, `_fmt_date`, `_fmt_money` (R3, R7); run test_greeting_uses_folded_first_name_only
- [ ] 5. GREEN: PROTECTED clauses + renewal date (R5); run persona tests for SYN-0001..0003
- [ ] 6. GREEN: AT_RISK shortfall month selection and due date fallback (R5); run test_dev_message, test_shortfall_*, test_due_date_*
- [ ] 7. GREEN: AT_RISK generic and NEEDS_REVIEW clauses (R5)
- [ ] 8. GREEN: `_fit` length strategy (drop optional clauses, compact variants, word-boundary cut) (R1)
- [ ] 9. Export sms_reminder from proofkit.integration.__init__
- [ ] 10. Run both files; all property tests green at 300 examples
- [ ] 11. REFACTOR: types, names; ruff; make check-contracts && make check-ownership
- [ ] 12. Run tests/integration suite; nothing previously green turns red
