---
inclusion: always
---
# ProofKit: test-driven development (docs/03_TDD_WORKFLOW.md)

## The loop: one behavior at a time
1. Pick the next behavior from the TDD order in `docs/roles/<ROLE>.md`. One behavior, not a feature.
2. RED: write or choose ONE failing test. Run only that test, for example
   `.venv/Scripts/python -m pytest tests/unit/wallet/test_wallet_spec.py::test_hours_basis_when_80_hours -q`.
   Show the user the failure output. It must fail for the right reason (NotImplementedError or an assertion, not an ImportError or a typo).
3. GREEN: write the minimum code that passes. Hard-coding for one cycle is fine if the next test forces the general case.
4. Run the module suite (`make test-p1a|test-p1b|test-p2|test-final`). Nothing that was green may turn red.
5. REFACTOR with everything green: names, extracted functions, types. Then run `make check-contracts` and `make check-ownership`.
6. Propose a small commit with the right prefix. The human commits; the guard hook blocks `git commit` from Kiro.

## Never
- Write implementation code before a failing test exists for it.
- Weaken, edit, skip, `xfail` or delete a test to get green. If a test looks wrong, explain why and wait for the user's approval.
- Mock the unit under test. Mock only the boundaries: `LLMClient` (use `FakeLLM`), the filesystem, the clock.
- Call a real LLM or the network outside `@pytest.mark.live`.
- Report work as done while any test in the module is red.

## Test design
- Pure functions (`evaluate_months`, `compute_deadlines`, `decide_exemption`, token parsers, ICD-10 normalization, the status backstop) get table-driven `@pytest.mark.parametrize` tests at the boundaries: exactly 80 h, exactly $580.00, lookback day 0 and day -1, month and year rollover, February 2028.
- Pure functions also get Hypothesis property tests once `hypothesis` is pinned (see tech.md). Example invariants:
  - shortfalls are >= 0, and `qualifies` holds exactly when `basis != none`;
  - prorated pieces sum to the source total to the cent;
  - `decide_exemption` returns the same decision for shuffled findings;
  - normalizing an ICD-10 code twice gives the same result as once.
- Use a callable `FakeLLM` response for retries, failures and routing.
- For every bug, first write a test that reproduces it, then fix it.
- Coverage of at least 85% per module is a floor, not the goal.

## Commit prefixes
- `test:` the failing test. `feat:` the implementation. `refactor:` cleanup with tests green.
- If they are tiny, the test and the implementation may share one commit. Keep commits small.

## Definition of done
- Spec and acceptance tests green, plus your own edge-case tests from the role doc.
- `make check-contracts`, `make check-ownership`, `make security` and ruff all clean.
- `HANDOFF.md` written in the module folder.
