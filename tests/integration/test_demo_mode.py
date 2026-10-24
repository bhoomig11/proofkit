"""
FINAL SPEC: offline demo mode (.kiro/specs/offline-demo, core slice).

The demo client replays recorded answers built from the golden fixtures, so every persona runs through the
public module APIs without an API key or a network connection. Requirement numbers refer to requirements.md.
"""
from __future__ import annotations

import socket
from decimal import Decimal

import pytest

from proofkit.common.config import Settings
from proofkit.contracts import DecisionOutcome
from proofkit.extraction import extract_findings
from proofkit.integration.demo import DEMO_SUMMARY, MODE_LABELS, choose_llm, demo_llm
from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules
from proofkit.wallet import build_wallet, load_wallet_rules

# Placeholder only. Deliberately does not look like a real Anthropic key.
PLACEHOLDER_KEY = "placeholder-not-a-real-key"


def _finding_fields(bundle):
    """FindingsBundle -> comparable tuples of (condition, status, quote, icd10), in order."""
    return [(f.condition, f.status, f.quote, f.icd10) for f in bundle.findings]


def _assert_months_match(wallet, expected_months, member_id):
    """WalletResult.months vs one persona's entry in fixtures/wallet/expected.json (qualifies, total_hours)."""
    by_month = {m.month: m for m in wallet.months}
    for month, exp in expected_months.items():
        assert month in by_month, (member_id, month)
        got = by_month[month]
        assert got.qualifies is exp["qualifies"], (member_id, month)
        assert got.total_hours == Decimal(exp["total_hours"]), (member_id, month)


def _persona_months(expected_wallet):
    """Only the per-member entries of expected.json (skip _why and the deadline keys)."""
    return {k: v for k, v in expected_wallet.items() if k.startswith("SYN-")}


# ─────────────────────────── Req 1.1, 1.2: findings replay ───────────────────────────
def test_demo_findings_match_golden_for_every_persona(notes_by_member, golden_findings):
    assert notes_by_member, "fixtures must contain notes"
    for member_id, notes in notes_by_member.items():
        bundle = extract_findings(notes, member_id, demo_llm())
        golden = golden_findings[member_id]
        assert bundle.member_id == member_id
        assert _finding_fields(bundle) == _finding_fields(golden), member_id


# ─────────────────────────── Req 2.1, 2.2: wallet replay ───────────────────────────
def test_demo_wallet_months_match_expected(members, earnings_docs_by_member, expected_wallet, demo_today,
                                           wallet_rules_path):
    rules = load_wallet_rules(wallet_rules_path)
    persona_months = _persona_months(expected_wallet)
    assert persona_months, "expected wallet must list personas"
    for member_id, expected_months in persona_months.items():
        wallet = build_wallet(members[member_id], earnings_docs_by_member.get(member_id, []), demo_llm(), rules,
                              demo_today)
        _assert_months_match(wallet, expected_months, member_id)


# ─────────────────────────── Req 3: statement for exempt personas ───────────────────────────
def test_demo_statement_for_exempt_personas(members, notes_by_member, demo_today, frailty_rules_path):
    rules = load_frailty_rules(frailty_rules_path)
    exempt_seen = []
    for member_id, notes in notes_by_member.items():
        member = members[member_id]
        bundle = extract_findings(notes, member_id, demo_llm())
        decision = decide_exemption(bundle, member, rules, demo_today)
        if decision.outcome != DecisionOutcome.EXEMPT:
            continue
        exempt_seen.append(member_id)
        statement = draft_statement(decision, bundle, member, demo_llm())
        assert statement, member_id
        assert DEMO_SUMMARY in statement, member_id
    assert exempt_seen, "at least one persona must be EXEMPT offline"


# ─────────────────────────── Req 4.1-4.4: mode selection ───────────────────────────
class _StubAnthropicClient:
    """Stands in for AnthropicClient so no live client is ever built in a test."""

    def __init__(self, settings=None):
        self.settings = settings

    def complete_json(self, *, task, instructions, untrusted_text=None):
        raise AssertionError("stub live client must not be called")


def _fake_settings(key):
    return Settings(anthropic_api_key=key, model="test-model", max_tokens=16, llm_timeout_s=1.0)


@pytest.mark.parametrize(
    ("demo", "env_demo", "key", "expected_mode"),
    [
        (True, None, None, "offline-demo"),               # 4.1 explicit demo
        (False, None, PLACEHOLDER_KEY, "live"),           # 4.2 explicit live with a key
        (None, "1", PLACEHOLDER_KEY, "offline-demo"),     # 4.3 PROOFKIT_DEMO=1 wins over a key
        (None, None, None, "offline-demo"),               # 4.4 no env, no key -> demo
        (None, None, PLACEHOLDER_KEY, "live"),            # 4.4 no env, key -> live
    ],
)
def test_choose_llm_mode_table(monkeypatch, demo, env_demo, key, expected_mode):
    import proofkit.integration.demo as demo_mod

    if env_demo is None:
        monkeypatch.delenv("PROOFKIT_DEMO", raising=False)
    else:
        monkeypatch.setenv("PROOFKIT_DEMO", env_demo)
    monkeypatch.setattr(demo_mod, "load_settings", lambda: _fake_settings(key))
    monkeypatch.setattr(demo_mod, "AnthropicClient", _StubAnthropicClient)

    client, mode = choose_llm(demo=demo)

    assert mode == expected_mode
    if expected_mode == "live":
        assert isinstance(client, _StubAnthropicClient)
    else:
        assert not isinstance(client, _StubAnthropicClient)


# ─────────────────────────── Req 4.6: labels ───────────────────────────
def test_mode_labels():
    assert MODE_LABELS == {"live": "Live LLM", "offline-demo": "Offline demo (recorded answers)"}


# ─────────────────────────── Req 5: no network ───────────────────────────
def test_demo_mode_opens_no_socket(monkeypatch, members, notes_by_member, earnings_docs_by_member,
                                   golden_findings, expected_wallet, demo_today, frailty_rules_path,
                                   wallet_rules_path):
    attempts = []

    def deny(*args, **kwargs):
        attempts.append(1)
        raise RuntimeError("network attempted in offline demo mode")

    monkeypatch.setattr(socket, "socket", deny)
    monkeypatch.setattr(socket, "create_connection", deny)
    monkeypatch.setattr(socket, "getaddrinfo", deny)

    frailty_rules = load_frailty_rules(frailty_rules_path)
    wallet_rules = load_wallet_rules(wallet_rules_path)
    persona_months = _persona_months(expected_wallet)

    for member_id, member in members.items():
        llm, mode = choose_llm(demo=True)
        assert mode == "offline-demo"

        notes = notes_by_member.get(member_id, [])
        if notes:
            bundle = extract_findings(notes, member_id, llm)
            assert _finding_fields(bundle) == _finding_fields(golden_findings[member_id]), member_id
            decision = decide_exemption(bundle, member, frailty_rules, demo_today)
            if decision.outcome == DecisionOutcome.EXEMPT:
                assert DEMO_SUMMARY in draft_statement(decision, bundle, member, llm), member_id

        wallet = build_wallet(member, earnings_docs_by_member.get(member_id, []), llm, wallet_rules, demo_today)
        if member_id in persona_months:
            _assert_months_match(wallet, persona_months[member_id], member_id)

    assert attempts == []
