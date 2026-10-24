"""
P1B owns this. DETERMINISTIC. This function takes NO LLM argument, by design.
An exemption decision must be reproducible and auditable from findings + rules + date alone.
"""
from __future__ import annotations

from datetime import date

from proofkit.contracts import ExemptionDecision, FindingsBundle, Member
from proofkit.reasoning.rules import FrailtyRules


def decide_exemption(bundle: FindingsBundle, member: Member, rules: FrailtyRules, as_of: date) -> ExemptionDecision:
    """FindingsBundle + Member + FrailtyRules + as_of -> ExemptionDecision."""
    raise NotImplementedError("P1B: implement test-first")
