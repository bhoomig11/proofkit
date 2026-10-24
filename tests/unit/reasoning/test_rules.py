"""P1B own tests: strict loading of config/frailty_rules.json."""
import json

import pytest

from proofkit.contracts import ExemptionType, FindingStatus
from proofkit.reasoning import load_frailty_rules


@pytest.fixture
def raw(frailty_rules_path):
    return json.loads(frailty_rules_path.read_text())


def write(tmp_path, data):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps(data))
    return p


def test_seed_config_loads_with_expected_values(frailty_rules_path):
    rules = load_frailty_rules(frailty_rules_path)
    assert rules.lookback_months.value == 12
    assert rules.min_finding_confidence == 0.6
    assert (rules.review_band.low, rules.review_band.high) == (0.6, 0.8)
    assert rules.counted_statuses == [FindingStatus.CURRENT]
    assert rules.review_statuses == [FindingStatus.UNCERTAIN]
    assert {r.exemption_type for r in rules.rules} == {ExemptionType.MEDICALLY_FRAIL}


def test_every_seed_rule_is_marked_verify(frailty_rules_path):
    rules = load_frailty_rules(frailty_rules_path)
    assert rules.lookback_months.verify
    assert all(r.verify for r in rules.rules)


def test_duplicate_rule_ids_rejected(tmp_path, raw):
    raw["rules"].append(dict(raw["rules"][0]))
    with pytest.raises(ValueError, match="duplicate rule_id"):
        load_frailty_rules(write(tmp_path, raw))


def test_empty_prefixes_rejected(tmp_path, raw):
    raw["rules"][0]["icd10_prefixes"] = []
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


@pytest.mark.parametrize("prefix", ["f31", "F", "F3", "31", "F31.", "F31.9X12A", " F31"])
def test_malformed_prefixes_rejected(tmp_path, raw, prefix):
    raw["rules"][0]["icd10_prefixes"] = [prefix]
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


def test_unknown_keys_rejected_but_comment_keys_allowed(tmp_path, raw):
    assert "_note" in raw  # the seed carries comment keys and still loads
    raw["surprise"] = 1
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


def test_rule_with_none_exemption_type_rejected(tmp_path, raw):
    raw["rules"][0]["exemption_type"] = "none"
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


def test_inverted_review_band_rejected(tmp_path, raw):
    raw["review_band"] = {"low": 0.9, "high": 0.5}
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


def test_no_rules_rejected(tmp_path, raw):
    raw["rules"] = []
    with pytest.raises(ValueError):
        load_frailty_rules(write(tmp_path, raw))


def test_rules_are_immutable(frailty_rules_path):
    rules = load_frailty_rules(frailty_rules_path)
    with pytest.raises(Exception):
        rules.rules_version = "tampered"
