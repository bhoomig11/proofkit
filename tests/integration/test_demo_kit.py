"""Demo kit (demo/): sample files for the offline end-to-end test, manual checks and the demo video.

Offline only: FakeLLM / demo_llm, no network, no live key. Member SYN-0099 is synthetic.
"""
from __future__ import annotations

import importlib.util
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest

from app.upload import to_document
from proofkit.common.llm import FakeLLM
from proofkit.contracts import ComplianceBasis, Member, WalletResult
from proofkit.integration.demo import demo_llm
from proofkit.wallet import build_wallet, load_wallet_rules

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "demo"
SAMPLES = DEMO / "samples"
SCRIPT = DEMO / "make_demo_kit.py"
DEMO_SCRIPT_MD = DEMO / "DEMO_SCRIPT.md"
RULES = load_wallet_rules(ROOT / "config" / "wallet_rules.json")
TODAY = date.fromisoformat(json.loads((ROOT / "fixtures" / "members" / "members.json")
                                      .read_text(encoding="utf-8"))["demo_today"])
MEMBER = Member(member_id="SYN-0099", display_name="Sam (synthetic)", renewal_date=date(2027, 3, 20))
MONTH = "2027-02"

SAMPLE_FILES = (
    "quickdash_feb_2027.csv",
    "ridenow_feb_2027.txt",
    "ridenow_feb_2027.pdf",
    "paystub_photo.png",
    "red_team_statement.txt",
    "clinical_note_maria.txt",
)
TEXT_SAMPLES = ("quickdash_feb_2027.csv", "ridenow_feb_2027.txt", "red_team_statement.txt",
                "clinical_note_maria.txt")
REAL_BRANDS = ("uber", "doordash", "instacart", "upwork", "taskrabbit")
DISCLAIMER = "RenewRight organizes evidence. MassHealth makes all eligibility determinations."
OFFLINE_COMMAND = ".venv/Scripts/python -m pytest tests/integration/test_demo_kit.py"


def _kit() -> ModuleType:
    """Load demo/make_demo_kit.py from its fixed repo path (demo/ is not a package)."""
    assert SCRIPT.is_file(), "demo/make_demo_kit.py is missing"
    spec = importlib.util.spec_from_file_location("make_demo_kit", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample(name: str) -> bytes:
    path = SAMPLES / name
    assert path.is_file(), f"demo/samples/{name} is missing"
    return path.read_bytes()


def _wallet(name: str, llm) -> WalletResult:
    doc = to_document(name, _sample(name), MEMBER.member_id, 0, RULES)
    return build_wallet(MEMBER, [doc], llm, RULES, TODAY)


def _month(wallet: WalletResult, month: str = MONTH):
    found = [m for m in wallet.months if m.month == month]
    assert len(found) == 1, f"expected exactly one {month} month, got {[m.month for m in wallet.months]}"
    return found[0]


def test_demo_kit_files_exist_and_are_regenerated_identically(tmp_path: Path) -> None:
    kit = _kit()
    kit.main([str(tmp_path)])
    kit.main([str(tmp_path)])  # idempotent: a second run gives the same bytes
    for name in SAMPLE_FILES:
        assert (tmp_path / name).read_bytes() == _sample(name), f"{name} differs from demo/samples/"
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(SAMPLE_FILES)


def test_csv_sample_qualifies_offline() -> None:
    llm = FakeLLM({})
    month = _month(_wallet("quickdash_feb_2027.csv", llm))
    assert month.qualifies
    assert month.basis == ComplianceBasis.INCOME
    assert month.total_income == Decimal("640.00")
    assert llm.calls == []


def test_ridenow_text_sample_gives_92_5_hours_offline() -> None:
    month = _month(_wallet("ridenow_feb_2027.txt", demo_llm()))
    assert month.total_hours == Decimal("92.50")
    assert month.qualifies
    assert month.basis == ComplianceBasis.HOURS


def test_ridenow_pdf_sample_is_read_but_needs_live_ai() -> None:
    """Offline replay only recognizes exact fixture text; PDF-extracted text differs, so it needs live AI."""
    doc = to_document("ridenow_feb_2027.pdf", _sample("ridenow_feb_2027.pdf"), MEMBER.member_id, 0, RULES)
    assert doc.doc_type.value == "pdf" and doc.content_b64
    wallet = build_wallet(MEMBER, [doc], demo_llm(), RULES, TODAY)
    assert wallet.records == []


def test_photo_sample_is_flagged_for_review() -> None:
    llm = FakeLLM({})
    wallet = _wallet("paystub_photo.png", llm)
    assert wallet.records == []
    assert _month(wallet).needs_review
    assert llm.calls == []


def test_photo_sample_is_a_valid_png() -> None:
    data = _sample("paystub_photo.png")
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    assert data.endswith(b"IEND\xaeB`\x82")


def test_red_team_sample_injection_is_ignored() -> None:
    llm = demo_llm()
    wallet = _wallet("red_team_statement.txt", llm)
    month = _month(wallet)
    assert month.total_hours == Decimal("30.00")
    assert month.total_income == Decimal("410.00")
    assert not month.qualifies
    for r in wallet.records:
        assert r.hours != Decimal("200")
        assert r.gross_income != Decimal("5000")
    # The injected document text travels only in the delimited user block, never in instructions.
    text = _sample("red_team_statement.txt").decode("utf-8")
    assert llm.calls
    for call in llm.calls:
        assert "<untrusted_document>" in call["user"]
        assert "200 hours" not in call["instructions"]
    assert "200 hours and $5,000" in text


def test_samples_use_only_fictional_brands() -> None:
    texts = {name: _sample(name).decode("utf-8").lower() for name in TEXT_SAMPLES}
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - pypdf is a pinned runtime dependency
        PdfReader = None
    if PdfReader is not None:
        reader = PdfReader(io.BytesIO(_sample("ridenow_feb_2027.pdf")))
        texts["ridenow_feb_2027.pdf"] = "\n".join(p.extract_text() or "" for p in reader.pages).lower()
        assert "ridenow" in texts["ridenow_feb_2027.pdf"]
    for name, text in texts.items():
        for brand in REAL_BRANDS:
            assert brand not in text, f"{name} mentions a real brand"


def test_samples_contain_only_synthetic_ids() -> None:
    import re

    for name in TEXT_SAMPLES:
        text = _sample(name).decode("utf-8")
        assert not re.search(r"\b\d{3}-\d{2}-\d{4}\b", text), f"{name} has an SSN-like number"


def test_demo_script_mentions_every_sample_and_the_disclaimer() -> None:
    assert DEMO_SCRIPT_MD.is_file(), "demo/DEMO_SCRIPT.md is missing"
    text = DEMO_SCRIPT_MD.read_text(encoding="utf-8")
    for name in SAMPLE_FILES:
        assert name in text, f"DEMO_SCRIPT.md does not mention {name}"
    assert DISCLAIMER in text
    assert OFFLINE_COMMAND in text
    assert "python demo/make_demo_kit.py" in text
    for expected in ("$640.00", "92.50", "30.00", "$410.00", "Process with live AI", "navigator"):
        assert expected in text, f"DEMO_SCRIPT.md does not state {expected}"
