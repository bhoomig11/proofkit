"""P1B owns this. Internal rules model (NOT a shared contract). Validate config/frailty_rules.json strictly."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from proofkit.contracts import ICD10_PATTERN, ExemptionType, FindingStatus

Fraction = Annotated[float, Field(ge=0.0, le=1.0)]
Icd10Prefix = Annotated[str, Field(pattern=ICD10_PATTERN)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Lookback(_Strict):
    value: int = Field(ge=1, le=60)
    verify: bool = True
    why: str = ""


class ReviewBand(_Strict):
    low: Fraction
    high: Fraction
    why: str = ""

    @model_validator(mode="after")
    def _ordered(self) -> "ReviewBand":
        if self.low > self.high:
            raise ValueError("review_band.low must be <= review_band.high")
        return self


class Rule(_Strict):
    rule_id: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1)
    exemption_type: ExemptionType
    label: str = Field(min_length=1)
    icd10_prefixes: list[Icd10Prefix] = Field(min_length=1)
    terms: list[str] = Field(default_factory=list, description="lowercase condition words, used to vet LLM text")
    verify: bool = True

    @field_validator("terms")
    @classmethod
    def _lowercase_terms(cls, v: list[str]) -> list[str]:
        if any(not t or t != t.strip().lower() for t in v):
            raise ValueError("terms must be non-empty, lowercase and trimmed")
        return v

    @field_validator("exemption_type")
    @classmethod
    def _not_none(cls, v: ExemptionType) -> ExemptionType:
        if v == ExemptionType.NONE:
            raise ValueError("a rule must grant a real exemption_type, not 'none'")
        return v


class FrailtyRules(_Strict):
    """Mirror of config/frailty_rules.json. Keys starting with '_' are comments and are ignored."""

    rules_version: str = Field(min_length=1)
    lookback_months: Lookback
    min_finding_confidence: Fraction
    review_band: ReviewBand
    counted_statuses: list[FindingStatus] = Field(min_length=1)
    review_statuses: list[FindingStatus] = Field(default_factory=list)
    rules: list[Rule] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _drop_comment_keys(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if not str(k).startswith("_")}
        return data

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "FrailtyRules":
        seen: set[str] = set()
        for rule in self.rules:
            if rule.rule_id in seen:
                raise ValueError(f"duplicate rule_id: {rule.rule_id}")
            seen.add(rule.rule_id)
        return self


def load_frailty_rules(path: Path) -> FrailtyRules:
    """Read and strictly validate a frailty rules JSON file -> FrailtyRules. Raises ValueError if invalid."""
    return FrailtyRules.model_validate(json.loads(Path(path).read_text()))
