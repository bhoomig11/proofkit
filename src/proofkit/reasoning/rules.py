"""P1B owns this. Internal rules model (NOT a shared contract). Validate config/frailty_rules.json strictly."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class FrailtyRules(BaseModel):
    """TODO(P1B): define fields mirroring config/frailty_rules.json (rules_version, lookback_months, rules[...])."""


def load_frailty_rules(path: Path) -> FrailtyRules:
    raise NotImplementedError("P1B: implement test-first")
