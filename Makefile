PY ?= python
PYTEST = $(PY) -m pytest

.PHONY: test test-p1a test-p1b test-p2 test-final check-contracts lock-contracts check-ownership security lint eval check fixtures

test:
	$(PYTEST)

test-p1a:
	$(PYTEST) tests/unit/extraction tests/acceptance/test_extraction_golden.py --cov=src/proofkit/extraction --cov-report=term-missing

test-p1b:
	$(PYTEST) tests/unit/reasoning tests/acceptance/test_reasoning_golden.py --cov=src/proofkit/reasoning --cov-report=term-missing

test-p2:
	$(PYTEST) tests/unit/wallet tests/acceptance/test_wallet_golden.py --cov=src/proofkit/wallet --cov-report=term-missing

test-final:
	$(PYTEST) tests/integration

check-contracts:
	$(PY) scripts/contract_lock.py
	$(PYTEST) tests/contract tests/unit/common

# ONLY after all 3 humans agreed to a contract change (docs/05_INTEGRATION.md)
lock-contracts:
	$(PY) scripts/contract_lock.py --write

check-ownership:
	$(PY) scripts/check_ownership.py

lint:
	ruff check src tests scripts

security:
	$(PY) scripts/scan_secrets.py
	-bandit -q -r src
	-pip-audit

eval:
	$(PY) eval/run_eval.py

fixtures:
	$(PY) scripts/build_fixtures.py

check: check-contracts check-ownership lint security test
