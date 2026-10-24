"""P1B ACCEPTANCE: golden findings -> expected decisions for all personas."""
from datetime import date

from proofkit.reasoning import decide_exemption, load_frailty_rules


def test_expected_decisions(golden_findings, members, expected_decisions, frailty_rules_path):
    rules = load_frailty_rules(frailty_rules_path)
    as_of = date.fromisoformat(expected_decisions["as_of"])
    for member_id, exp in expected_decisions["expected"].items():
        d = decide_exemption(golden_findings[member_id], members[member_id], rules, as_of)
        assert d.outcome.value == exp["outcome"], member_id
        assert d.exemption_type.value == exp["exemption_type"], member_id
        assert sorted(m.rule_id for m in d.matched_rules) == sorted(exp["rule_ids"]), member_id
        assert sorted(d.evidence_finding_ids) == sorted(exp["evidence_finding_ids"]), member_id
        assert d.lookback_months == expected_decisions["lookback_months"]
