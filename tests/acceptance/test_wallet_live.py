"""P2 LIVE smoke test: real LLM on the synthetic Uber statement. Opt-in: pytest -m live tests/acceptance/test_wallet_live.py"""
from decimal import Decimal

import pytest

from proofkit.common.llm import AnthropicClient, LLMError
from proofkit.wallet import build_wallet, load_wallet_rules


@pytest.mark.live
def test_uber_statement_with_real_llm(members, earnings_docs_by_member, wallet_rules_path, demo_today):
    try:
        llm = AnthropicClient()
    except LLMError:
        pytest.skip("ANTHROPIC_API_KEY not set")
    (doc,) = [d for d in earnings_docs_by_member["SYN-0002"] if d.doc_id == "D-0002-uber-feb"]
    w = build_wallet(members["SYN-0002"], [doc], llm, load_wallet_rules(wallet_rules_path), demo_today)
    # Output varies run to run, so check only what grounding guarantees plus a loose expectation.
    assert w.records and all(r.platform == "uber" for r in w.records)
    m = {m.month: m for m in w.months}["2027-02"]
    assert m.total_hours == Decimal("92.50") and m.total_income in {Decimal("1480.00"), Decimal("1592.00")}
