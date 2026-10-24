"""
P1B SPEC TESTS. They start RED. Make them green one at a time (/tdd).
"""
from datetime import date

import pytest

from proofkit.common.llm import FakeLLM
from proofkit.contracts import (DecisionOutcome, ExemptionType, Finding, FindingsBundle, FindingStatus, Member)
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules

AS_OF = date(2027, 3, 1)
MEMBER = Member(member_id="SYN-0001", display_name="Maria (synthetic)", renewal_date=date(2027, 3, 20))


def finding(icd="M32.9", status=FindingStatus.CURRENT, d=date(2026, 11, 10), conf=0.95, fid="F1", quote="lupus"):
    return Finding(finding_id=fid, note_id="N1", note_date=d, condition="c", icd10=icd, status=status,
                   quote=quote, quote_start=0, quote_end=len(quote), confidence=conf)


def bundle(*findings, member_id="SYN-0001"):
    return FindingsBundle(member_id=member_id, notes_processed=["N1"], findings=list(findings), extractor_version="t")


@pytest.fixture
def rules(frailty_rules_path):
    return load_frailty_rules(frailty_rules_path)


def test_rules_load_and_reject_bad_config(tmp_path, rules):
    assert rules is not None
    bad = tmp_path / "bad.json"
    bad.write_text('{"rules_version": "x", "rules": [{"rule_id": "R", "icd10_prefixes": []}]}')
    with pytest.raises(Exception):
        load_frailty_rules(bad)


def test_current_qualifying_condition_is_exempt(rules):
    d = decide_exemption(bundle(finding("M32.14")), MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.EXEMPT
    assert d.exemption_type == ExemptionType.MEDICALLY_FRAIL
    assert [m.rule_id for m in d.matched_rules] == ["MF-AI-01"]
    assert d.evidence_finding_ids == ["F1"]


@pytest.mark.parametrize("status", [FindingStatus.NEGATED, FindingStatus.RULED_OUT,
                                    FindingStatus.FAMILY_HISTORY, FindingStatus.HISTORICAL])
def test_non_current_statuses_never_count(rules, status):
    d = decide_exemption(bundle(finding("I50.9", status=status)), MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.NOT_EXEMPT


def test_uncertain_qualifying_condition_goes_to_review(rules):
    d = decide_exemption(bundle(finding("F20.9", status=FindingStatus.UNCERTAIN)), MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.NEEDS_CLINICIAN_REVIEW
    assert d.review_reasons


def test_lookback_window_is_inclusive_and_excludes_older(rules):
    on_boundary = finding("M32.9", d=date(2026, 3, 1))
    too_old = finding("M32.9", d=date(2026, 2, 28))
    assert decide_exemption(bundle(on_boundary), MEMBER, rules, AS_OF).outcome == DecisionOutcome.EXEMPT
    assert decide_exemption(bundle(too_old), MEMBER, rules, AS_OF).outcome == DecisionOutcome.NOT_EXEMPT


def test_future_dated_findings_ignored(rules):
    d = decide_exemption(bundle(finding("M32.9", d=date(2027, 4, 1))), MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.NOT_EXEMPT


def test_confidence_band(rules):
    assert decide_exemption(bundle(finding(conf=0.5)), MEMBER, rules, AS_OF).outcome == DecisionOutcome.NOT_EXEMPT
    assert decide_exemption(bundle(finding(conf=0.7)), MEMBER, rules, AS_OF).outcome == DecisionOutcome.NEEDS_CLINICIAN_REVIEW
    assert decide_exemption(bundle(finding(conf=0.9)), MEMBER, rules, AS_OF).outcome == DecisionOutcome.EXEMPT


@pytest.mark.parametrize("icd,should_match", [("F31.9", True), ("F3", False), ("F32.9", False), ("F33.2", True), ("M321", False)])
def test_prefix_matching_respects_code_boundaries(rules, icd, should_match):
    try:
        f = finding(icd)
    except Exception:
        assert not should_match
        return
    d = decide_exemption(bundle(f), MEMBER, rules, AS_OF)
    assert (d.outcome == DecisionOutcome.EXEMPT) == should_match


def test_strongest_evidence_wins_and_all_matching_evidence_listed(rules):
    d = decide_exemption(bundle(finding("M32.9", fid="A"), finding("F33.2", fid="B"), finding("J30.2", fid="C")),
                         MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.EXEMPT
    assert set(d.evidence_finding_ids) == {"A", "B"}


def test_no_findings_is_not_exempt(rules):
    d = decide_exemption(bundle(), MEMBER, rules, AS_OF)
    assert d.outcome == DecisionOutcome.NOT_EXEMPT and d.exemption_type == ExemptionType.NONE


def test_member_mismatch_raises(rules):
    with pytest.raises(ValueError):
        decide_exemption(bundle(member_id="SYN-0002"), MEMBER, rules, AS_OF)


def test_deterministic(rules):
    b = bundle(finding("M32.9"), finding("F33.2", fid="B"))
    assert decide_exemption(b, MEMBER, rules, AS_OF) == decide_exemption(b, MEMBER, rules, AS_OF)


def test_statement_uses_llm_summary_and_cites_quotes(rules):
    b = bundle(finding("M32.14", quote="Systemic lupus erythematosus with lupus nephritis"))
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    llm = FakeLLM({"draft_statement": {"summary": "Patient has active systemic lupus with kidney involvement."}})
    s = draft_statement(d, b, MEMBER, llm)
    assert "Systemic lupus erythematosus with lupus nephritis" in s      # evidence quote cited
    assert "M32.14" in s
    assert "active systemic lupus" in s                                  # LLM summary used
    assert "must be reviewed and signed by a licensed clinician" in s.lower()


def test_statement_rejects_llm_summary_that_invents_conditions(rules):
    b = bundle(finding("M32.14"))
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    llm = FakeLLM({"draft_statement": {"summary": "Patient also has schizophrenia (F20.9)."}})
    s = draft_statement(d, b, MEMBER, llm)
    assert "F20.9" not in s and "schizophrenia" not in s.lower()


def test_statement_refused_for_not_exempt(rules):
    d = decide_exemption(bundle(), MEMBER, rules, AS_OF)
    with pytest.raises(ValueError):
        draft_statement(d, bundle(), MEMBER, FakeLLM({}))
