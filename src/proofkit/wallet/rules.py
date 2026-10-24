"""P2 owns this. Internal rules model. Validate config/wallet_rules.json. Income threshold must equal wage x hours."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class WalletRules(BaseModel):
    """TODO(P2): fields mirroring config/wallet_rules.json. Use Decimal for money and hours."""


def load_wallet_rules(path: Path) -> WalletRules:
    raise NotImplementedError("P2: implement test-first")
