"""P1B own tests: decide_exemption must stay pure (no LLM, no clock, no I/O)."""
import ast
import inspect
from pathlib import Path

import proofkit.reasoning.decide as decide_mod
import proofkit.reasoning.match as match_mod
import proofkit.reasoning.rules as rules_mod

DECISION_MODULES = [decide_mod, match_mod]
FORBIDDEN_IMPORTS = ("proofkit.common.llm", "proofkit.extraction", "proofkit.wallet", "anthropic")
FORBIDDEN_CALLS = {"today", "now", "utcnow", "open", "read_text", "read_bytes", "urlopen"}


def imported_modules(mod) -> set[str]:
    tree = ast.parse(Path(mod.__file__).read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def called_attributes(mod) -> set[str]:
    tree = ast.parse(Path(mod.__file__).read_text())
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            out.add(fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", ""))
    return out


def test_decision_modules_import_no_llm_or_other_modules():
    for mod in DECISION_MODULES + [rules_mod]:
        bad = [m for m in imported_modules(mod) if m.startswith(FORBIDDEN_IMPORTS)]
        assert not bad, f"{mod.__name__} imports {bad}"


def test_decision_modules_call_no_clock_or_io():
    for mod in DECISION_MODULES:
        bad = called_attributes(mod) & FORBIDDEN_CALLS
        assert not bad, f"{mod.__name__} calls {bad}"


def test_decide_exemption_takes_no_llm_parameter():
    params = list(inspect.signature(decide_mod.decide_exemption).parameters)
    assert params == ["bundle", "member", "rules", "as_of"]


def test_eval_code_does_not_import_other_modules_or_the_llm():
    import eval.metrics as metrics_mod
    import eval.run_eval as run_eval_mod
    for mod in (metrics_mod, run_eval_mod):
        bad = [m for m in imported_modules(mod) if m.startswith(FORBIDDEN_IMPORTS)]
        assert not bad, f"{mod.__name__} imports {bad}"
