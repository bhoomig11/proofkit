"""Coverage Coach facts are written for members: no rule IDs, codes or confidence numbers, no suspected
diagnoses named in chat, and what-if wording a person can follow."""
import re
from datetime import date

import pytest

from proofkit.contracts import DecisionOutcome, ExemptionDecision, ExemptionType
from proofkit.integration import ask_coach, run_member
from proofkit.wallet import load_wallet_rules
from tests.acceptance.test_extraction_golden import sloppy_llm_from_golden
from tests.acceptance.test_wallet_golden import replay_llm
from tests.integration.test_coach import coach_llm, facts
from tests.integration.test_end_to_end import RoutingLLM


@pytest.fixture
def ctx(members, notes_by_member, earnings_docs_by_member, golden_findings, golden_records, demo_today,
        frailty_rules_path, wallet_rules_path):
    """The real pipeline for a persona, offline: what the app hands the coach."""
    def build(member_id):
        llm = RoutingLLM(sloppy_llm_from_golden(golden_findings[member_id]), replay_llm(golden_records))
        status = run_member(members[member_id], notes_by_member.get(member_id, []),
                            earnings_docs_by_member.get(member_id, []), llm, frailty_rules_path,
                            wallet_rules_path, demo_today)
        return {"member": members[member_id], "status": status,
                "wallet_rules": load_wallet_rules(wallet_rules_path), "today": demo_today}
    return build

ICD10 = re.compile(r"\b[A-Z]\d{2}(?:\.[0-9A-Z]{1,4})?\b")


def _no_jargon(text: str) -> None:
    assert not ICD10.search(text), text
    assert "MF-" not in text and "confidence" not in text.lower(), text


def test_why_for_an_exempt_member_is_plain_and_points_to_the_evidence_tab(ctx):
    reply = ask_coach("Why am I exempt?", llm=coach_llm({"tool": "show_evidence", "args": {}}), **ctx("SYN-0001"))
    _no_jargon(facts(reply))
    assert "medically frail" in facts(reply)
    assert "Evidence tab" in facts(reply)


def test_clinician_review_case_never_names_the_suspected_condition(ctx):
    c = ctx("SYN-0001")
    review = ExemptionDecision(
        member_id="SYN-0001", outcome=DecisionOutcome.NEEDS_CLINICIAN_REVIEW, exemption_type=ExemptionType.NONE,
        confidence=0.8, matched_rules=[], evidence_finding_ids=["F-N-0001-a-0"], lookback_months=12,
        as_of=date(2027, 3, 1), rules_version="seed",
        review_reasons=["Possible Bipolar disorder: F31.9 is documented as uncertain (confidence 0.80) in note "
                        "N-0001-a on 2026-11-10. A clinician should confirm."])
    c["status"] = c["status"].model_copy(update={"exemption": review})
    reply = ask_coach("Why?", llm=coach_llm({"tool": "show_evidence", "args": {}}), **c)
    _no_jargon(facts(reply))
    assert "bipolar" not in facts(reply).lower() and "N-0001-a" not in facts(reply)
    assert "clinician" in facts(reply).lower()


def test_what_if_wording_is_plain_and_keeps_the_result(ctx):
    llm = coach_llm({"tool": "what_if", "args": {"month": "2027-02", "extra_income": "60"}})
    reply = ask_coach("What if I earn $60 more?", llm=llm, **ctx("SYN-0004"))
    assert reply.facts[0].startswith("Just checking, nothing is saved.")
    assert "What-if only" not in facts(reply)
    assert "would be protected" in facts(reply).lower()  # phrase other tests and the UI rely on


def test_what_if_for_someone_already_protected_says_so(ctx):
    llm = coach_llm({"tool": "what_if", "args": {"month": "2027-02", "extra_income": "60"}})
    reply = ask_coach("What if I earn $60 more?", llm=llm, **ctx("SYN-0001"))
    assert "already protected" in facts(reply).lower()
    assert "would be protected" not in facts(reply).lower()
