"""P2 owns this. Internal rules model. Validate config/wallet_rules.json. Income threshold must equal wage x hours."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from proofkit.contracts import DocumentType


class WalletRules(BaseModel):
    """Validated, flattened view of config/wallet_rules.json. Money and hours are Decimal."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rules_version: str = Field(min_length=1)
    monthly_hours_required: Decimal = Field(gt=0)
    federal_minimum_wage: Decimal = Field(gt=0)
    monthly_income_required: Decimal = Field(gt=0)
    allow_seasonal_income_averaging: bool
    averaging_window_months: int = Field(ge=1, le=12)
    verification_months_before_renewal: int = Field(ge=1, le=3)
    proof_buffer_days: int = Field(ge=0, le=90)
    min_record_confidence: float = Field(ge=0, le=1)
    requirements_start_date: date
    known_platforms: frozenset[str]
    max_bytes: int = Field(gt=0)
    allowed_doc_types: frozenset[DocumentType]
    max_pdf_pages: int = Field(gt=0)

    @model_validator(mode="after")
    def _income_is_derived(self) -> "WalletRules":
        if self.monthly_income_required != self.federal_minimum_wage * self.monthly_hours_required:
            raise ValueError("monthly_income_required must equal federal_minimum_wage * monthly_hours_required")
        return self


def load_wallet_rules(path: Path) -> WalletRules:
    """Load config/wallet_rules.json into a WalletRules. Raises on any inconsistency."""
    cfg = json.loads(Path(path).read_text(), parse_float=Decimal)
    averaging = cfg["allow_seasonal_income_averaging"]
    limits = cfg["upload_limits"]
    return WalletRules(
        rules_version=cfg["rules_version"],
        monthly_hours_required=cfg["monthly_hours_required"]["value"],
        federal_minimum_wage=cfg["federal_minimum_wage"]["value"],
        monthly_income_required=cfg["monthly_income_required"]["value"],
        allow_seasonal_income_averaging=averaging["value"],
        averaging_window_months=averaging["averaging_window_months"],
        verification_months_before_renewal=cfg["verification_months_before_renewal"]["value"],
        proof_buffer_days=cfg["proof_buffer_days"]["value"],
        min_record_confidence=cfg["min_record_confidence"],
        requirements_start_date=cfg["requirements_start_date"]["value"],
        known_platforms=cfg["known_platforms"],
        max_bytes=limits["max_bytes"],
        allowed_doc_types=limits["allowed_doc_types"],
        max_pdf_pages=limits["max_pdf_pages"],
    )
