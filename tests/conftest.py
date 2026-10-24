"""FROZEN shared test setup: network blocking, fixture loaders, FakeLLM helpers."""
from __future__ import annotations

import json
import socket
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
CONFIG = ROOT / "config"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: calls the real LLM/network (opt-in: pytest -m live)")
    config.addinivalue_line("markers", "slow: slow test")


@pytest.fixture(autouse=True)
def _block_network(request, monkeypatch):
    """Every test is offline unless marked @pytest.mark.live."""
    if request.node.get_closest_marker("live"):
        return

    def guard(*args, **kwargs):
        raise RuntimeError("Network access in a non-live test. Use FakeLLM or mark @pytest.mark.live")

    monkeypatch.setattr(socket.socket, "connect", guard)
    monkeypatch.setattr(socket, "create_connection", guard)


def _load(p: Path):
    return json.loads(p.read_text())


@pytest.fixture
def demo_today() -> date:
    return date.fromisoformat(_load(FIXTURES / "members" / "members.json")["demo_today"])


@pytest.fixture
def members():
    from proofkit.contracts import Member
    return {m["member_id"]: Member.model_validate(m) for m in _load(FIXTURES / "members" / "members.json")["members"]}


@pytest.fixture
def notes_by_member():
    from proofkit.contracts import ClinicalNote
    out: dict[str, list] = {}
    for p in sorted((FIXTURES / "notes").glob("*.json")):
        n = ClinicalNote.model_validate(_load(p))
        out.setdefault(n.member_id, []).append(n)
    return out


@pytest.fixture
def golden_findings():
    from proofkit.contracts import FindingsBundle
    return {p.name.split(".")[0]: FindingsBundle.model_validate(_load(p))
            for p in sorted((FIXTURES / "findings").glob("*.golden.json"))}


@pytest.fixture
def earnings_docs_by_member():
    from proofkit.contracts import EarningsDocument
    out: dict[str, list] = {}
    for p in sorted((FIXTURES / "earnings_docs").glob("*.json")):
        d = EarningsDocument.model_validate(_load(p))
        out.setdefault(d.member_id, []).append(d)
    return out


@pytest.fixture
def golden_records():
    from proofkit.contracts import EarningsRecord
    return {p.name.split(".")[0]: [EarningsRecord.model_validate(r) for r in _load(p)]
            for p in sorted((FIXTURES / "earnings").glob("*.golden.json"))}


@pytest.fixture
def expected_decisions():
    return _load(FIXTURES / "decisions" / "expected.json")


@pytest.fixture
def expected_wallet():
    return _load(FIXTURES / "wallet" / "expected.json")


@pytest.fixture
def expected_status():
    return _load(FIXTURES / "members" / "expected_status.json")


@pytest.fixture
def frailty_rules_path() -> Path:
    return CONFIG / "frailty_rules.json"


@pytest.fixture
def wallet_rules_path() -> Path:
    return CONFIG / "wallet_rules.json"


@pytest.fixture
def fake_llm():
    from proofkit.common.llm import FakeLLM
    return FakeLLM()
