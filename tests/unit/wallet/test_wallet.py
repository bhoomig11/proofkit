from datetime import date
from decimal import Decimal as D

import pytest

from proofkit.common.llm import FakeLLM
from proofkit.contracts import ComplianceBasis, EarningsDocument, Member
from proofkit.wallet import build_wallet, load_wallet_rules

TODAY = date(2027, 3, 1)
MEMBER = Member(member_id="SYN-0001", display_name="x", renewal_date=date(2027, 3, 20))


@pytest.fixture
def rules(wallet_rules_path):
    return load_wallet_rules(wallet_rules_path)


def csv_doc(doc_id, row, member="SYN-0001"):
    return EarningsDocument(doc_id=doc_id, member_id=member, filename="w.csv", doc_type="csv",
                            content_text=f"platform,period_start,period_end,hours,gross_pay\n{row}\n")


def test_zero_docs_gives_empty_months_but_deadlines(rules):
    w = build_wallet(MEMBER, [], FakeLLM({}), rules, TODAY)
    assert (w.records, w.months) == ([], [])
    assert (w.verification_months, w.proof_due_date, w.next_renewal_date) == (["2027-02"], date(2027, 3, 6),
                                                                              date(2027, 3, 20))
    assert w.member_id == "SYN-0001" and w.rules_version == rules.rules_version


def test_four_weekly_statements_sum_to_the_month(rules):
    weeks = [(1, 7), (8, 14), (15, 21), (22, 28)]
    docs = [csv_doc(f"wk{i}", f"quickdash,2027-02-{a:02},2027-02-{b:02},20,150.00") for i, (a, b) in enumerate(weeks)]
    (m,) = build_wallet(MEMBER, docs, FakeLLM({}), rules, TODAY).months
    assert (m.total_hours, m.total_income, m.basis, m.needs_review) == (D("80.00"), D("600.00"),
                                                                        ComplianceBasis.HOURS, False)
    assert len(m.record_ids) == 4


def test_unread_image_flags_the_verification_month(rules):
    img = EarningsDocument(doc_id="img1", member_id="SYN-0001", filename="p.png", doc_type="image", content_b64="iVBO")
    w = build_wallet(MEMBER, [img], FakeLLM({}), rules, TODAY)
    (m,) = w.months
    assert m.month == "2027-02" and not m.qualifies and m.needs_review
    assert any("img1" in r for r in m.review_reasons)


def test_image_flag_is_added_to_an_existing_month(rules):
    img = EarningsDocument(doc_id="img1", member_id="SYN-0001", filename="p.png", doc_type="image", content_b64="iVBO")
    docs = [csv_doc("c1", "quickdash,2027-02-01,2027-02-28,90,700.00"), img]
    (m,) = build_wallet(MEMBER, docs, FakeLLM({}), rules, TODAY).months
    assert m.qualifies and m.total_hours == D("90.00") and m.needs_review


def test_rejected_upload_is_not_swallowed(rules):
    with pytest.raises(ValueError):
        build_wallet(MEMBER, [csv_doc("c1", "quickdash,2027-02-01,2027-02-28,90,700.00", member="SYN-0002")],
                     FakeLLM({}), rules, TODAY)
