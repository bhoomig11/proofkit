---
inclusion: always
---
# ProofKit: tech

## Language and types
- Python 3.11+ (`requires-python >=3.11`, ruff target py311, line length 120). Use type hints everywhere and pure functions where possible. No global mutable state.
- pydantic 2.9.2. Contract models are `extra="forbid"` and `frozen=True`: construct new instances, never mutate.
- Money and hours are `decimal.Decimal`, never float. In JSON, write them as strings (`"598.20"`). Round half-up only at the end.
- Dates are `datetime.date`. Pass `today` / `as_of` in as parameters. Rules code never calls `date.today()`.
- Inject every boundary: `LLMClient`, `today`/`as_of`, and the rules config.
- Configurable values live in `config/*.json`. Every unchecked value carries `"verify": true`.
- Public functions have docstrings naming the contract model they take and return.

## Dependencies (pinned in pyproject.toml)
- Runtime: pydantic==2.9.2, anthropic==0.39.0, python-dotenv==1.0.1, pypdf==5.1.0.
- dev: pytest==8.3.3, pytest-cov==5.0.0, ruff==0.7.1, bandit==1.7.10, pip-audit==2.7.3, pre-commit==4.0.1. ui: streamlit==1.39.0.
- Add no dependency without telling the user. Pin exact versions.

## Tests
- pytest with `addopts = -q -m 'not live' --strict-markers`. Markers: `live` (opt-in, `pytest -m live`) and `slow`.
- Unit, contract and acceptance tests use `FakeLLM` from `proofkit.common.llm`: a canned dict, or a callable `(instructions, untrusted_text) -> value` for retries and failures. Assert on `llm.calls`.
- Live tests check only contract validity plus a loose expectation.
- Property tests use Hypothesis. It is NOT in pyproject.toml yet. Before the first property test, ask the user to add a pinned `hypothesis==<version>` to the dev extras on main. Don't add it yourself.
- Coverage is >= 85% for each of `extraction/`, `reasoning/` and `wallet/`.

## Make targets
| Target | Runs |
|---|---|
| `test` | the whole suite |
| `test-p1a` / `test-p1b` / `test-p2` | module unit + golden acceptance tests with coverage |
| `test-final` | `tests/integration` |
| `check-contracts` | `scripts/contract_lock.py` + `tests/contract` + `tests/unit/common` |
| `lock-contracts` | only after all 3 humans agree to a contract change |
| `check-ownership` | `scripts/check_ownership.py` |
| `lint` | `ruff check src tests scripts` |
| `security` | `scripts/scan_secrets.py`, bandit, pip-audit |
| `eval` | `eval/run_eval.py` |
| `check` | check-contracts, check-ownership, lint, security, test (the merge gate) |

## Windows
- Run make as `mingw32-make <target> PY=.venv/Scripts/python.exe`.
- Run tests directly with `.venv/Scripts/python -m pytest <path> -q`.
- `make lint` and `make security` call `ruff`, `bandit` and `pip-audit` from PATH, and security ignores their failures. Run them explicitly: `.venv/Scripts/python -m ruff check src tests scripts`, `.venv/Scripts/python -m bandit -q -r src`, `.venv/Scripts/pip-audit`.
- Set up with `bash setup/install.sh --copy` and `py -3.11 -m venv .venv`.
