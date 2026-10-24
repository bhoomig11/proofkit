"""What-if slider: real wallet rules on a copy; the real status never changes."""
from decimal import Decimal
from pathlib import Path

from app.data import load_demo_data
from app.state import build_member_view, make_llm
from app.whatif import what_if_status
from proofkit.contracts import OverallStatus
from proofkit.wallet import load_wallet_rules

ROOT = Path(__file__).resolve().parents[2]


def view_for(member_id):
    data = load_demo_data(ROOT)
    llm, _ = make_llm(live=False, data=data)
    view = build_member_view(member_id, data, llm, ROOT / "config/frailty_rules.json", ROOT / "config/wallet_rules.json")
    return data, view


def test_dev_plus_60_dollars_becomes_protected_without_changing_real_status():
    data, view = view_for("SYN-0004")
    rules = load_wallet_rules(ROOT / "config/wallet_rules.json")
    before = view.status.model_copy(deep=True)
    after = what_if_status(view, rules, data.today, extra_hours=Decimal("0"), extra_income=Decimal("60"))
    assert view.status.status == OverallStatus.AT_RISK and after.status == OverallStatus.PROTECTED
    assert view.status == before


def test_too_little_extra_stays_at_risk():
    data, view = view_for("SYN-0004")
    rules = load_wallet_rules(ROOT / "config/wallet_rules.json")
    after = what_if_status(view, rules, data.today, extra_hours=Decimal("1"), extra_income=Decimal("10"))
    assert after.status == OverallStatus.AT_RISK


def test_nothing_added_returns_the_real_status():
    data, view = view_for("SYN-0005")
    rules = load_wallet_rules(ROOT / "config/wallet_rules.json")
    assert what_if_status(view, rules, data.today, extra_hours=Decimal("0"), extra_income=Decimal("0")) == view.status
