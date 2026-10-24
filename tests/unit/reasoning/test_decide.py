"""P1B own tests for decide_exemption, beyond the spec."""
from datetime import date

import pytest

from proofkit.contracts import DecisionOutcome, ExemptionType, Finding, FindingsBundle, FindingStatus, Member
from proofkit.reasoning import decide_exemption, load_frailty_rules
from proofkit.reasoning.match import icd_matches

AS_OF = date(2027, 3, 1)
MEMBER = Member(member_id="SYN-0001", display_name="Maria (synthetic)", renewal_date=date(2027, 3, 20))


def finding(icd="M32.9", status=FindingStatus.CURRENT, d=date(2026, 11, 10), conf=0.95, fid="F1", note="N1"):
    return Finding(finding_id=fid, note_id=note, note_date=d, condition="c", icd10=icd, status=status,
                   quote="q", quote_start=0, quote_end=1, confidence=conf)


def decide(*findings, as_of=AS_OF, rules=None):
    b = FindingsBundle(member_id="SYN-0001", notes_processed=["N1"], findings=list(findings), extractor_version="t")
    return decide_exemption(b, MEMBER, rules, as_of)


@pytest.fixture
def rules(frailty_rules_path):
    return load_frailty_rules(frailty_rules_path)


# ── review outcome ──────────────────────────────────────────────────────────
def test_review_decision_lists_candidates_without_claiming_an_exemption(rules):
    d = decide(finding("F20.9", status=FindingStatus.UNCERTAIN, conf=0.85, fid="U1", note="N-7"), rules=rules)
    assert d.outcome == DecisionOutcome.NEEDS_CLINICIAN_REVIEW
    assert d.exemption_type == ExemptionType.NONE
    assert d.matched_rules == []
    assert d.evidence_finding_ids == ["U1"]
    assert d.confidence == 0.85
    reason = d.review_reasons[0]
    assert "Schizophrenia spectrum" in reason and "F20.9" in reason and "N-7" in reason


def test_uncertain_condition_matching_no_rule_is_not_exempt(rules):
    d = decide(finding("J45.20", status=FindingStatus.UNCERTAIN), rules=rules)
    assert d.outcome == DecisionOutcome.NOT_EXEMPT


def test_counting_evidence_beats_review(rules):
    d = decide(finding("M32.9", fid="A"), finding("F20.9", status=FindingStatus.UNCERTAIN, fid="B"), rules=rules)
    assert d.outcome == DecisionOutcome.EXEMPT
    assert d.evidence_finding_ids == ["A"]
    assert d.review_reasons == []


# ── lookback window (calendar months, inclusive, day clamped to month end) ──
def with_lookback(rules, months):
    return rules.model_copy(update={"lookback_months": rules.lookback_months.model_copy(update={"value": months})})


@pytest.mark.parametrize("as_of,months,first_day_in", [
    (date(2027, 3, 31), 1, date(2027, 2, 28)),    # Mar 31 − 1 month → Feb 28
    (date(2028, 3, 31), 1, date(2028, 2, 29)),    # leap year → Feb 29
    (date(2028, 2, 29), 12, date(2027, 2, 28)),   # leap day − 12 months → Feb 28
    (date(2027, 1, 15), 1, date(2026, 12, 15)),   # crosses the year
    (date(2027, 3, 1), 12, date(2026, 3, 1)),     # the spec's own boundary
])
def test_lookback_month_end_boundaries(rules, as_of, months, first_day_in):
    r = with_lookback(rules, months)
    day_before = date.fromordinal(first_day_in.toordinal() - 1)
    assert decide(finding(d=first_day_in), as_of=as_of, rules=r).outcome == DecisionOutcome.EXEMPT
    assert decide(finding(d=day_before), as_of=as_of, rules=r).outcome == DecisionOutcome.NOT_EXEMPT


def test_finding_dated_on_as_of_counts(rules):
    assert decide(finding(d=AS_OF), rules=rules).outcome == DecisionOutcome.EXEMPT


@pytest.mark.parametrize("months,expected", [(6, DecisionOutcome.NOT_EXEMPT), (12, DecisionOutcome.NOT_EXEMPT),
                                             (24, DecisionOutcome.EXEMPT)])
def test_lookback_sweep_on_a_current_finding_18_months_old(rules, months, expected):
    old = finding("F33.2", d=date(2025, 9, 1))      # 18 months before AS_OF
    assert decide(old, rules=with_lookback(rules, months)).outcome == expected


def test_decision_reports_the_lookback_it_used(rules):
    assert decide(finding(), rules=with_lookback(rules, 24)).lookback_months == 24


# ── future-dated findings ───────────────────────────────────────────────────
def test_finding_dated_one_day_after_as_of_is_ignored(rules):
    assert decide(finding(d=date(2027, 3, 2)), rules=rules).outcome == DecisionOutcome.NOT_EXEMPT


def test_future_uncertain_finding_does_not_trigger_review(rules):
    f = finding("F20.9", status=FindingStatus.UNCERTAIN, d=date(2027, 6, 1))
    assert decide(f, rules=rules).outcome == DecisionOutcome.NOT_EXEMPT


# ── confidence band (seed: min 0.6, review [0.6, 0.8), counts >= 0.8) ────────
@pytest.mark.parametrize("conf,expected", [
    (0.0, DecisionOutcome.NOT_EXEMPT), (0.59, DecisionOutcome.NOT_EXEMPT),
    (0.6, DecisionOutcome.NEEDS_CLINICIAN_REVIEW), (0.79, DecisionOutcome.NEEDS_CLINICIAN_REVIEW),
    (0.8, DecisionOutcome.EXEMPT), (1.0, DecisionOutcome.EXEMPT),
])
def test_confidence_band_boundaries(rules, conf, expected):
    assert decide(finding(conf=conf), rules=rules).outcome == expected


def test_low_confidence_current_finding_review_reason_says_why(rules):
    d = decide(finding("M32.9", conf=0.7), rules=rules)
    assert "Systemic lupus erythematosus" in d.review_reasons[0] and "0.70" in d.review_reasons[0]


def test_uncertain_below_minimum_confidence_is_dropped(rules):
    f = finding("F20.9", status=FindingStatus.UNCERTAIN, conf=0.5)
    assert decide(f, rules=rules).outcome == DecisionOutcome.NOT_EXEMPT


def test_mid_confidence_non_qualifying_condition_is_not_exempt(rules):
    assert decide(finding("J30.2", conf=0.7), rules=rules).outcome == DecisionOutcome.NOT_EXEMPT


# ── prefix matching on code boundaries ──────────────────────────────────────
@pytest.mark.parametrize("code,prefix,expected", [
    ("F31.9", "F31", True), ("F31", "F31", True), ("F31.81", "F31", True),
    ("F32.9", "F32.2", False), ("F32.2", "F32.2", True), ("F32.29", "F32.2", True),
    ("F43.10", "F43.1", True), ("F43.2", "F43.1", False), ("F32", "F32.2", False),
    ("M32.14", "M32", True), ("M05.79", "M06", False), ("C50.911", "C50", True),
])
def test_icd_matches_respects_code_boundaries(code, prefix, expected):
    assert icd_matches(code, prefix) is expected


# ── evidence, grouping, determinism ─────────────────────────────────────────
def test_multiple_rules_listed_sorted_with_their_own_evidence(rules):
    d = decide(finding("M32.9", fid="L2", conf=0.85), finding("F33.2", fid="D1", conf=0.9),
               finding("M32.14", fid="L1", conf=0.95), rules=rules)
    assert d.outcome == DecisionOutcome.EXEMPT
    assert [(m.rule_id, m.finding_ids) for m in d.matched_rules] == [("MF-AI-01", ["L1", "L2"]), ("MF-MH-03", ["D1"])]
    assert d.evidence_finding_ids == ["D1", "L1", "L2"]
    assert d.confidence == 0.95


def test_input_order_does_not_change_the_decision(rules):
    fs = [finding("M32.9", fid="A"), finding("F33.2", fid="B"), finding("F20.9", status=FindingStatus.UNCERTAIN, fid="C")]
    assert decide(*fs, rules=rules) == decide(*reversed(fs), rules=rules)


@pytest.mark.parametrize("status", [FindingStatus.NEGATED, FindingStatus.RULED_OUT,
                                    FindingStatus.FAMILY_HISTORY, FindingStatus.HISTORICAL])
def test_non_current_statuses_never_count_or_trigger_review_even_at_full_confidence(rules, status):
    d = decide(finding("F20.9", status=status, conf=1.0), rules=rules)
    assert d.outcome == DecisionOutcome.NOT_EXEMPT and d.review_reasons == []


def test_decision_carries_rules_version_and_as_of(rules):
    d = decide(finding(), rules=rules)
    assert d.rules_version == rules.rules_version and d.as_of == AS_OF
