"""Offline, deterministic tests for the UI's member-view pipeline."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from proofkit.contracts import DecisionOutcome, OverallStatus

from app.data import load_demo_data
from app.state import build_member_view, make_llm

ROOT = Path(__file__).resolve().parents[2]


def test_demo_data_contains_only_the_five_synthetic_personas() -> None:
    data = load_demo_data(ROOT)
    assert sorted(data.members) == [f"SYN-{number:04d}" for number in range(1, 6)]
    assert all(note.member_id == member_id for member_id, notes in data.notes.items() for note in notes)
    assert all(doc.member_id == member_id for member_id, docs in data.documents.items() for doc in docs)


def test_every_persona_builds_to_expected_status_offline() -> None:
    data = load_demo_data(ROOT)
    llm, is_live = make_llm(live=False, data=data)
    assert is_live is False
    for member_id, expected in data.expected_status.items():
        view = build_member_view(
            member_id,
            data,
            llm,
            ROOT / "config" / "frailty_rules.json",
            ROOT / "config" / "wallet_rules.json",
        )
        assert view.status.status.value == expected["status"], member_id
        assert view.status.protected_by == expected["protected_by"], member_id
        assert view.status.member_id == member_id


def test_adversarial_persona_injections_do_not_change_result() -> None:
    data = load_demo_data(ROOT)
    llm, _ = make_llm(live=False, data=data)
    view = build_member_view(
        "SYN-0005",
        data,
        llm,
        ROOT / "config" / "frailty_rules.json",
        ROOT / "config" / "wallet_rules.json",
    )
    assert view.status.status == OverallStatus.AT_RISK
    assert view.exemption.outcome == DecisionOutcome.NOT_EXEMPT
    assert not any(finding.icd10.startswith("F20") for finding in view.findings.findings)
    february = next(month for month in view.wallet.months if month.month == "2027-02")
    assert (february.total_hours, february.total_income, february.qualifies) == (
        Decimal("30.00"), Decimal("410.00"), False
    )


def test_unknown_persona_is_rejected() -> None:
    data = load_demo_data(ROOT)
    llm, _ = make_llm(live=False, data=data)
    try:
        build_member_view("SYN-9999", data, llm, ROOT / "config/frailty_rules.json",
                          ROOT / "config/wallet_rules.json")
    except ValueError as exc:
        assert "unknown synthetic persona" in str(exc)
    else:
        raise AssertionError("unknown persona was accepted")
