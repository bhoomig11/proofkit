"""
P1B owns this. DETERMINISTIC. This function takes NO LLM argument, by design.
An exemption decision must be reproducible and auditable from findings + rules + date alone.
"""
from __future__ import annotations

from datetime import date

from proofkit.contracts import (DecisionOutcome, ExemptionDecision, ExemptionType, Finding, FindingsBundle,
                                MatchedRule, Member)
from proofkit.reasoning.rules import FrailtyRules, Rule


def _matching_rules(finding: Finding, rules: FrailtyRules) -> list[Rule]:
    return [r for r in rules.rules if any(finding.icd10.startswith(p) for p in r.icd10_prefixes)]


def decide_exemption(bundle: FindingsBundle, member: Member, rules: FrailtyRules, as_of: date) -> ExemptionDecision:
    """FindingsBundle + Member + FrailtyRules + as_of -> ExemptionDecision."""
    if bundle.member_id != member.member_id:
        raise ValueError("bundle.member_id does not match member.member_id")

    counting: dict[str, list[Finding]] = {}
    rule_by_id: dict[str, Rule] = {}
    for f in bundle.findings:
        if f.status not in rules.counted_statuses:
            continue
        for rule in _matching_rules(f, rules):
            counting.setdefault(rule.rule_id, []).append(f)
            rule_by_id[rule.rule_id] = rule

    common = dict(member_id=member.member_id, lookback_months=rules.lookback_months.value, as_of=as_of,
                  rules_version=rules.rules_version)
    if not counting:
        return ExemptionDecision(outcome=DecisionOutcome.NOT_EXEMPT, exemption_type=ExemptionType.NONE,
                                 confidence=0.0, matched_rules=[], evidence_finding_ids=[], **common)

    matched = [MatchedRule(rule_id=rid, category=rule_by_id[rid].category,
                           finding_ids=sorted(f.finding_id for f in fs),
                           rationale=f"Current {rule_by_id[rid].label} documented")
               for rid, fs in sorted(counting.items())]
    evidence = sorted({f.finding_id for fs in counting.values() for f in fs})
    return ExemptionDecision(outcome=DecisionOutcome.EXEMPT, exemption_type=rule_by_id[matched[0].rule_id].exemption_type,
                             confidence=max(f.confidence for fs in counting.values() for f in fs),
                             matched_rules=matched, evidence_finding_ids=evidence, **common)
