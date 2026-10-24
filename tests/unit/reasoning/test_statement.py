"""P1B own tests for draft_statement, beyond the spec."""
from datetime import date

import pytest

from proofkit.common.llm import FakeLLM, LLMError
from proofkit.contracts import DecisionOutcome, Finding, FindingsBundle, FindingStatus, Member
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules

AS_OF = date(2027, 3, 1)
MEMBER = Member(member_id="SYN-0001", display_name="Maria (synthetic)", renewal_date=date(2027, 3, 20))
LUPUS_QUOTE = "Systemic lupus erythematosus with lupus nephritis"


def finding(icd="M32.14", status=FindingStatus.CURRENT, conf=0.95, fid="F1", quote=LUPUS_QUOTE,
            condition="Systemic lupus erythematosus with organ involvement", note="N-0001-a"):
    return Finding(finding_id=fid, note_id=note, note_date=date(2026, 11, 10), condition=condition, icd10=icd,
                   status=status, quote=quote, quote_start=0, quote_end=len(quote), confidence=conf)


def bundle(*fs, member_id="SYN-0001"):
    return FindingsBundle(member_id=member_id, notes_processed=["N-0001-a"], findings=list(fs or [finding()]),
                          extractor_version="t")


@pytest.fixture
def rules(frailty_rules_path):
    return load_frailty_rules(frailty_rules_path)


def draft(summary, b=None, rules=None):
    b = b or bundle()
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    llm = FakeLLM({"draft_statement": summary if callable(summary) else {"summary": summary}})
    return draft_statement(d, b, MEMBER, llm), llm


GOOD = "Patient has active systemic lupus with kidney involvement requiring ongoing treatment."


def test_template_has_every_required_part(rules):
    s, _ = draft(GOOD, rules=rules)
    for part in ["MEDICAL FRAILTY STATEMENT", "Maria (synthetic)", "SYN-0001", "2027-03-01", "12 months",
                 f'M32.14 — Systemic lupus erythematosus with organ involvement — "{LUPUS_QUOTE}" (N-0001-a, 2026-11-10)',
                 "MF-AI-01", "Systemic lupus erythematosus", GOOD, "Signature:", "Date:",
                 "must be reviewed and signed by a licensed clinician", "MassHealth makes all eligibility determinations"]:
        assert part in s, part
    assert len(s) <= 5000


def test_quotes_reach_the_llm_only_through_the_untrusted_channel(rules):
    _, llm = draft(GOOD, rules=rules)
    call = llm.calls[0]
    assert call["task"] == "draft_statement"
    assert LUPUS_QUOTE not in call["instructions"]
    assert LUPUS_QUOTE in call["user"] and "<untrusted_document>" in call["user"]


@pytest.mark.parametrize("bad", [
    "Patient has lupus and heart failure.",                   # a condition from another rule
    "Patient has lupus (M32.14) and also I50.9.",            # an ICD code not in the evidence
    "History suggests possible psychosis.",                    # another rule's term
    "",                                                        # empty
    "x" * 1201,                                                # too long
])
def test_invalid_summaries_fall_back_to_template(rules, bad):
    s, _ = draft(bad, rules=rules)
    assert bad not in s if bad else "Clinical summary:\n\n" not in s
    assert "The medical record documents Systemic lupus erythematosus with organ involvement (M32.14)" in s


def test_summary_may_use_terms_of_the_matched_rule_and_evidence_codes(rules):
    ok = "Lupus (SLE, M32.14) with nephritis is documented and active."
    s, _ = draft(ok, rules=rules)
    assert ok in s


def test_term_check_is_word_bounded(rules):
    ok = "Lupus is active; the patient remains aidsless-free of new symptoms."   # 'aids' inside a word
    s, _ = draft("Lupus is active and the patient is self-sufficient.", rules=rules)
    assert "self-sufficient" in s
    assert "aidsless" in draft(ok, rules=rules)[0]


@pytest.mark.parametrize("resp", [
    lambda i, t: (_ for _ in ()).throw(LLMError("boom")),     # LLM failure
    ["not", "a", "dict"],                                      # wrong JSON type
    {"summary": 42},                                           # wrong field type
    {"text": GOOD},                                            # missing field
])
def test_llm_failures_fall_back_to_template(rules, resp):
    s, _ = draft(resp, rules=rules)
    assert "The medical record documents" in s


def test_review_decision_produces_a_marked_review_draft(rules):
    b = bundle(finding("F20.9", status=FindingStatus.UNCERTAIN, fid="U1", quote="? schizophrenia",
                       condition="Schizophrenia, unspecified"))
    s, _ = draft("Possible schizophrenia noted; diagnosis not confirmed.", b=b, rules=rules)
    assert "NEEDS CLINICIAN REVIEW" in s and "Possible Schizophrenia spectrum" in s
    assert "Possible schizophrenia noted" in s


def test_evidence_missing_from_bundle_raises(rules):
    b = bundle()
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    with pytest.raises(ValueError):
        draft_statement(d, bundle(finding(fid="OTHER")), MEMBER, FakeLLM({"draft_statement": {"summary": GOOD}}))


def test_member_mismatch_raises(rules):
    b = bundle()
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    other = Member(member_id="SYN-0002", display_name="James (synthetic)", renewal_date=date(2027, 3, 20))
    with pytest.raises(ValueError):
        draft_statement(d, b, other, FakeLLM({"draft_statement": {"summary": GOOD}}))


def test_many_long_findings_stay_under_the_contract_limit(rules):
    fs = [finding(fid=f"F{i:02d}", quote="lupus " * 80) for i in range(40)]
    s, _ = draft(GOOD, b=bundle(*fs), rules=rules)
    assert len(s) <= 5000 and "more finding(s)" in s


def test_statement_is_deterministic(rules):
    assert draft(GOOD, rules=rules)[0] == draft(GOOD, rules=rules)[0]


def test_statement_fits_in_the_decision_contract(rules):
    b = bundle()
    d = decide_exemption(b, MEMBER, rules, AS_OF)
    s = draft_statement(d, b, MEMBER, FakeLLM({"draft_statement": {"summary": GOOD}}))
    assert d.model_copy(update={"statement_draft": s}).outcome == DecisionOutcome.EXEMPT
    type(d).model_validate({**d.model_dump(), "statement_draft": s})


def test_sign_off_survives_worst_case_length(rules):
    long_cond = "Systemic lupus erythematosus " + "with extensive multi-organ involvement " * 4
    fs = [finding(fid=f"U{i:02d}", status=FindingStatus.UNCERTAIN, quote="lupus " * 80, condition=long_cond[:200])
          for i in range(12)]
    s, _ = draft("Lupus " * 190, b=bundle(*fs), rules=rules)
    assert len(s) <= 5000
    assert s.rstrip().endswith("MassHealth makes all eligibility determinations.")
    assert "must be reviewed and signed by a licensed clinician" in s
