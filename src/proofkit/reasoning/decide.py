"""
P1B owns this. DETERMINISTIC. This function takes NO LLM argument, by design.
An exemption decision must be reproducible and auditable from findings + rules + date alone.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date

from proofkit.contracts import (DecisionOutcome, ExemptionDecision, ExemptionType, Finding, FindingsBundle,
                                MatchedRule, Member)
from proofkit.reasoning.match import icd_matches
from proofkit.reasoning.rules import FrailtyRules, Rule


@dataclass
class _Triage:
    counting: dict[str, list[Finding]] = field(default_factory=dict)   # rule_id -> findings that count
    rules: dict[str, Rule] = field(default_factory=dict)               # rule_id -> rule, for counting rules
    review: list[tuple[Finding, list[Rule]]] = field(default_factory=list)


def months_before(d: date, months: int) -> date:
    """Same day `months` calendar months earlier, clamped to that month's last day (Mar 31 - 1 -> Feb 28)."""
    year, month0 = divmod(d.year * 12 + (d.month - 1) - months, 12)
    month = month0 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _matching_rules(finding: Finding, rules: FrailtyRules) -> list[Rule]:
    return [r for r in rules.rules if any(icd_matches(finding.icd10, p) for p in r.icd10_prefixes)]


def _triage(findings: list[Finding], rules: FrailtyRules, as_of: date) -> _Triage:
    """Sort each in-window, confident-enough, rule-matching finding into 'counts' or 'review'; ignore the rest."""
    t = _Triage()
    window_start = months_before(as_of, rules.lookback_months.value)
    for f in sorted(findings, key=lambda f: f.finding_id):
        if not window_start <= f.note_date <= as_of or f.confidence < rules.min_finding_confidence:
            continue
        matching = _matching_rules(f, rules)
        if not matching:
            continue
        counted_status = f.status in rules.counted_statuses
        if counted_status and f.confidence >= rules.review_band.high:
            for rule in matching:
                t.counting.setdefault(rule.rule_id, []).append(f)
                t.rules[rule.rule_id] = rule
        elif counted_status or f.status in rules.review_statuses:
            t.review.append((f, matching))
    return t


def _review_reason(f: Finding, matching: list[Rule]) -> str:
    labels = ", ".join(r.label for r in sorted(matching, key=lambda r: r.rule_id))
    return (f"Possible {labels}: {f.icd10} is documented as {f.status.value} "
            f"(confidence {f.confidence:.2f}) in note {f.note_id} on {f.note_date.isoformat()}. "
            f"A clinician should confirm.")


def _rationale(rule: Rule, findings: list[Finding]) -> str:
    codes = ", ".join(sorted({f.icd10 for f in findings}))
    return f"Current {rule.label} ({codes}) documented in {len(findings)} finding(s) within the lookback window."[:500]


def decide_exemption(bundle: FindingsBundle, member: Member, rules: FrailtyRules, as_of: date) -> ExemptionDecision:
    """FindingsBundle + Member + FrailtyRules + as_of -> ExemptionDecision.

    EXEMPT if any current finding matches a rule with confidence >= review_band.high; else
    NEEDS_CLINICIAN_REVIEW if any matching finding is current-but-borderline or uncertain; else NOT_EXEMPT.
    """
    if bundle.member_id != member.member_id:
        raise ValueError("bundle.member_id does not match member.member_id")

    t = _triage(bundle.findings, rules, as_of)
    common = dict(member_id=member.member_id, lookback_months=rules.lookback_months.value, as_of=as_of,
                  rules_version=rules.rules_version)

    if t.counting:
        matched = [MatchedRule(rule_id=rid, category=t.rules[rid].category,
                               finding_ids=sorted(f.finding_id for f in fs), rationale=_rationale(t.rules[rid], fs))
                   for rid, fs in sorted(t.counting.items())]
        # strongest evidence wins: the exemption type comes from the rule backed by the most confident finding
        best_rule_id = max(sorted(t.counting), key=lambda rid: max(f.confidence for f in t.counting[rid]))
        return ExemptionDecision(outcome=DecisionOutcome.EXEMPT, exemption_type=t.rules[best_rule_id].exemption_type,
                                 confidence=max(f.confidence for fs in t.counting.values() for f in fs),
                                 matched_rules=matched,
                                 evidence_finding_ids=sorted({f.finding_id for fs in t.counting.values() for f in fs}),
                                 **common)

    if t.review:
        return ExemptionDecision(outcome=DecisionOutcome.NEEDS_CLINICIAN_REVIEW, exemption_type=ExemptionType.NONE,
                                 confidence=max(f.confidence for f, _ in t.review), matched_rules=[],
                                 evidence_finding_ids=sorted({f.finding_id for f, _ in t.review}),
                                 review_reasons=[_review_reason(f, m) for f, m in t.review], **common)

    return ExemptionDecision(outcome=DecisionOutcome.NOT_EXEMPT, exemption_type=ExemptionType.NONE,
                             confidence=0.0, matched_rules=[], evidence_finding_ids=[], **common)
