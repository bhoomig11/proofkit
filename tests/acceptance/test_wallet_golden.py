"""P2 ACCEPTANCE: golden records -> expected months; full docs -> golden records (with a replaying FakeLLM)."""
from decimal import Decimal

from proofkit.common.llm import FakeLLM
from proofkit.wallet import compute_deadlines, evaluate_months, load_wallet_rules, parse_documents


def test_golden_records_give_expected_months(golden_records, expected_wallet, wallet_rules_path):
    rules = load_wallet_rules(wallet_rules_path)
    for member_id, recs in golden_records.items():
        months = {m.month: m for m in evaluate_months(recs, rules)}
        for month, exp in expected_wallet[member_id].items():
            m = months[month]
            assert m.total_hours == Decimal(exp["total_hours"]), (member_id, month)
            assert m.total_income == Decimal(exp["total_income"]), (member_id, month)
            assert m.qualifies == exp["qualifies"] and m.basis.value == exp["basis"], (member_id, month)
            if "shortfall_income" in exp:
                assert m.shortfall_income == Decimal(exp["shortfall_income"])


def test_deadlines_match_expected(members, expected_wallet, wallet_rules_path):
    rules = load_wallet_rules(wallet_rules_path)
    months, due = compute_deadlines(members["SYN-0001"], rules)
    assert months == expected_wallet["verification_months_for_renewal_2027-03-20"]
    assert due.isoformat() == expected_wallet["proof_due_date_for_renewal_2027-03-20"]


def replay_llm(golden_records):
    by_doc = {}
    for recs in golden_records.values():
        for r in recs:
            by_doc.setdefault(r.source_doc_id, []).append({
                "platform": r.platform.upper(), "period_start": r.period_start.isoformat(),
                "period_end": r.period_end.isoformat(), "hours": None if r.hours is None else str(r.hours),
                "gross_income": str(r.gross_income), "source_quote": r.source_quote, "confidence": r.confidence})

    def respond(instructions, untrusted):
        for items in by_doc.values():
            if all(i["source_quote"] in (untrusted or "") for i in items):
                return {"records": items}
        return {"records": []}
    return FakeLLM({"extract_earnings": respond})


def test_parse_recovers_golden(earnings_docs_by_member, golden_records):
    llm = replay_llm(golden_records)
    for member_id, docs in earnings_docs_by_member.items():
        out = parse_documents(docs, member_id, llm)
        got = sorted((r.source_doc_id, r.platform, r.hours, r.gross_income) for r in out)
        want = sorted((r.source_doc_id, r.platform, r.hours, r.gross_income) for r in golden_records[member_id])
        assert got == want, member_id
