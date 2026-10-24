"""P2 LIVE smoke tests: a real LLM on the synthetic statements. Opt-in: pytest -m live tests/acceptance/test_wallet_live.py

Uses Groq when GROQ_API_KEY is set (GROQ_MODEL picks the model), otherwise Anthropic via common.config.
Live output varies run to run, so these check only what grounding guarantees plus loose expectations.
"""
import json
import os
import time
import urllib.error
import urllib.request
from decimal import Decimal

import pytest

from proofkit.common.llm import UNTRUSTED_GUARD, AnthropicClient, LLMError, parse_json_response, wrap_untrusted
from proofkit.wallet import build_wallet, load_wallet_rules


class GroqClient:
    """Test-only LLMClient for Groq's OpenAI-compatible API. Builds the prompt exactly like AnthropicClient."""

    def __init__(self, key: str, model: str):
        self.key, self.model = key, model

    def complete_json(self, *, task, instructions, untrusted_text=None):
        user = instructions if untrusted_text is None else f"{instructions}\n\n{wrap_untrusted(untrusted_text)}"
        body = {"model": self.model, "temperature": 0, "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": f"{UNTRUSTED_GUARD}\n\nTask: {task}"},
                             {"role": "user", "content": user}]}
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json",
                                              "User-Agent": "proofkit-live-test"})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return parse_json_response(json.load(resp)["choices"][0]["message"]["content"])
            except urllib.error.HTTPError as e:  # free tier is 8k tokens/min: wait out a 429, then retry
                if e.code != 429 or attempt == 2:
                    raise LLMError(f"groq call failed: HTTP {e.code}") from e
                time.sleep(min(float(e.headers.get("retry-after") or 30), 65))
            except OSError as e:  # network errors: same failure type as the real client
                raise LLMError(f"groq call failed: {type(e).__name__}") from e


@pytest.fixture
def llm():
    if key := os.environ.get("GROQ_API_KEY"):
        return GroqClient(key, os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"))
    try:
        return AnthropicClient()
    except LLMError:
        pytest.skip("no GROQ_API_KEY or ANTHROPIC_API_KEY set")


@pytest.fixture
def rules(wallet_rules_path):
    return load_wallet_rules(wallet_rules_path)


@pytest.mark.live
def test_ridenow_statement_with_real_llm(llm, rules, members, earnings_docs_by_member, demo_today):
    (doc,) = [d for d in earnings_docs_by_member["SYN-0002"] if d.doc_id == "D-0002-ridenow-feb"]
    w = build_wallet(members["SYN-0002"], [doc], llm, rules, demo_today)
    assert w.records and all(r.platform == "ridenow" for r in w.records)
    m = {m.month: m for m in w.months}["2027-02"]
    assert m.total_hours == Decimal("92.50") and m.total_income in {Decimal("1480.00"), Decimal("1592.00")}


@pytest.mark.live
def test_injected_statement_with_real_llm(llm, rules, members, earnings_docs_by_member, demo_today):
    w = build_wallet(members["SYN-0005"], earnings_docs_by_member["SYN-0005"], llm, rules, demo_today)
    for m in w.months:
        assert m.total_hours <= Decimal("30.00") and m.total_income <= Decimal("410.00") and not m.qualifies
    assert all(r.hours != Decimal("200") and r.gross_income != Decimal("5000") for r in w.records)


@pytest.mark.live
def test_every_persona_pass_fail_with_real_llm(llm, rules, members, earnings_docs_by_member, expected_wallet,
                                               demo_today):
    for member_id, docs in earnings_docs_by_member.items():
        w = build_wallet(members[member_id], docs, llm, rules, demo_today)
        months = {m.month: m for m in w.months}
        for month, exp in expected_wallet[member_id].items():
            assert month in months, (member_id, month)
            assert months[month].qualifies == exp["qualifies"], (member_id, month)
            assert months[month].total_hours == Decimal(exp["total_hours"]), (member_id, month)
