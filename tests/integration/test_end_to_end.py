"""
FINAL SPEC: the whole pipeline for each persona, with replaying FakeLLMs (offline, deterministic).
This file is the integration target. It goes green only when P1A + P1B + P2 + FINAL all work together.
"""
from datetime import date

from proofkit.common.llm import FakeLLM
from proofkit.contracts import OverallStatus
from proofkit.integration import run_member
from tests.acceptance.test_extraction_golden import sloppy_llm_from_golden
from tests.acceptance.test_wallet_golden import replay_llm


class RoutingLLM:
    """Routes each task to the right replaying fake. Mirrors how one real LLM client serves all modules."""

    def __init__(self, extraction, wallet):
        self.extraction, self.wallet = extraction, wallet
        self.statement = FakeLLM({"draft_statement": {"summary": "Findings in the record support this exemption."}})

    def complete_json(self, *, task, instructions, untrusted_text=None):
        target = {"extract_findings": self.extraction, "extract_earnings": self.wallet,
                  "draft_statement": self.statement}[task]
        return target.complete_json(task=task, instructions=instructions, untrusted_text=untrusted_text)


def test_every_persona_end_to_end(members, notes_by_member, earnings_docs_by_member, golden_findings,
                                  golden_records, expected_status, demo_today, frailty_rules_path, wallet_rules_path):
    for member_id, member in members.items():
        llm = RoutingLLM(sloppy_llm_from_golden(golden_findings[member_id]), replay_llm(golden_records))
        st = run_member(member, notes_by_member.get(member_id, []), earnings_docs_by_member.get(member_id, []),
                        llm, frailty_rules_path, wallet_rules_path, demo_today)
        exp = expected_status[member_id]
        assert st.status.value == exp["status"], member_id
        assert st.protected_by == exp["protected_by"], member_id
        if st.status == OverallStatus.AT_RISK:
            assert st.action_items and st.next_deadline is not None, member_id
        if st.exemption and st.exemption.outcome.value == "exempt":
            assert st.exemption.statement_draft, member_id
