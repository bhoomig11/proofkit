# 03: Test-driven workflow for Claude Code

## Why this matters here
Three AI sessions write code at the same time. Tests are how each one knows it's right **without seeing the others**. The contract tests guarantee the pieces fit together, and the acceptance tests guarantee they do the right thing.

## The test pyramid in this repo
| Layer | Location | Owner | Runs | Starts |
|---|---|---|---|---|
| Contract | `tests/contract/`, `tests/unit/common/` | frozen | every commit | **green** |
| Unit spec | `tests/unit/<module>/test_*_spec.py` | module owner | every change | **red** (by design) |
| Your own unit tests | `tests/unit/<module>/test_*.py` | module owner | every change | you write them |
| Acceptance (golden) | `tests/acceptance/test_<module>_golden.py` | module owner | before merge | red |
| Integration | `tests/integration/` | FINAL | after merges | red |
| Live (real LLM) | marked `@pytest.mark.live` | anyone | manually, `pytest -m live` | opt-in |

## The loop (use `/tdd <behavior>` in Claude Code)
1. **Pick the next behavior.** Use the order in your role doc. Choose one behavior, not a feature.
2. **RED.** Write the test, or pick the next red spec test. Run *only that test*: `pytest tests/unit/wallet/test_wallet_spec.py::test_hours_basis_when_80_hours`. Confirm it fails **for the right reason** (NotImplementedError or an assertion, not an ImportError typo).
3. **GREEN.** Write the minimum code that passes. Hard-coding is allowed for one cycle if the next test will force the general solution.
4. **Run the module suite**, e.g. `make test-p2`. Nothing that was green may turn red.
5. **REFACTOR.** Clean up names, extract functions, and add types. Stay green. Run `make check-contracts && make check-ownership`.
6. **Commit.** `test: ...` for the test, `feat: ...` for the implementation (or both together, if they're tiny). Commit often; integration is easier with small diffs.

## Rules for Claude Code (in CLAUDE.md, repeated here)
- No implementation without a failing test first.
- Never edit a spec test to make it pass. If it looks wrong, say so and wait for the human.
- No real network or LLM in tests. Use `FakeLLM`. Use a callable response to simulate retries, failures, or routing.
- Mock only boundaries (LLM, clock, filesystem), never your own logic.
- Pure functions get **table-driven tests** (`@pytest.mark.parametrize`) that cover boundaries: exactly 80 hours, exactly $580.00, lookback day 0 and day −1, month and year rollover.
- For every bug you find: first write a test that reproduces it, then fix it.
- Coverage target for your module: ≥ 85% lines (`make test-<role>` prints it). Coverage is a floor, not the goal.

## Writing good tests with FakeLLM
```python
from proofkit.common.llm import FakeLLM, LLMError
llm = FakeLLM({"extract_findings": {"findings": [...]}})            # canned
llm = FakeLLM({"extract_findings": lambda instr, text: {...}})       # computed from input
def flaky(instr, text): raise LLMError("bad json")                    # failure path
assert "<untrusted_document>" in llm.calls[0]["user"]                 # security assertion
```

## Live smoke test (optional, once per module, at the end)
Write one `@pytest.mark.live` test that runs your module on a single fixture with `AnthropicClient()` and checks only *contract validity* plus a loose expectation. Live LLM output varies from run to run, so don't assert exact values in live tests.

## Definition of done (every module)
- [ ] All spec tests and acceptance tests are green
- [ ] Your own extra tests cover the edge cases in your role doc
- [ ] `make check-contracts`, `make check-ownership`, `make security`, `ruff` all clean
- [ ] `/handoff` run and `HANDOFF.md` written
