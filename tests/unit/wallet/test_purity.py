"""evaluate_months and compute_deadlines decide outcomes, so they must stay pure: no LLM, no I/O, no clock."""
import ast
from pathlib import Path

import pytest

import proofkit.wallet as wallet

ALLOWED_IMPORTS = {"__future__", "datetime", "decimal", "typing", "proofkit.contracts", "proofkit.wallet.rules"}
BANNED_CALLS = {"today", "now", "utcnow", "open", "print", "input", "read_text", "read_bytes", "complete_json"}


@pytest.mark.parametrize("module", ["qualify.py", "deadlines.py"])
def test_decision_modules_are_pure(module):
    tree = ast.parse((Path(wallet.__file__).parent / module).read_text())
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imports |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    assert imports <= ALLOWED_IMPORTS, imports - ALLOWED_IMPORTS
    calls = {getattr(n.func, "attr", getattr(n.func, "id", None)) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not calls & BANNED_CALLS, calls & BANNED_CALLS
