"""
FINAL RED: Spanish and Portuguese SMS reminders.

New signature: sms_reminder(member, status, lang: str = "en") -> str.
- lang is one of "en", "es", "pt"; anything else raises ValueError.
- The default "en" output stays byte-identical to today's.
- Every language keeps R1-R7: <= 160 printable ASCII chars (no accents, so the SMS stays GSM-7 single-segment),
  folded first name only, no ids / phone digits / last name / conditions / codes / exemption types / program names,
  the AT_RISK shortfall as "$60.00", deterministic.
- Greetings: es "Hola <first>,", pt "Ola <first>,".
- Dates: es "6 mar 2027" (ene feb mar abr may jun jul ago sep oct nov dic),
         pt "6 mar 2027" (jan fev mar abr mai jun jul ago set out nov dez).

Persona builders and the oracle come from test_reminder.py; Hypothesis strategies and builders from
test_reminder_properties.py, so all three files share one reading of the spec.
"""
from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
import pytest

from proofkit.integration.reminder import sms_reminder
from tests.integration.test_reminder import (  # noqa: F401  (personas is a fixture)
    PERSONA_IDS,
    SMS_LIMIT,
    assert_no_forbidden_words,
    expected_first_name,
    personas,
)
from tests.integration.test_reminder_properties import (
    arbitrary_names,
    build_member,
    build_status,
    conditions,
    member_ids,
    phones,
    scenarios,
)

GREETINGS = {"es": "Hola", "pt": "Ola"}
I18N_LANGS = sorted(GREETINGS)


def assert_printable_ascii(msg: object) -> None:
    """R1 + R2 for any language."""
    assert isinstance(msg, str) and msg
    assert len(msg) <= SMS_LIMIT, f"{len(msg)} chars: {msg!r}"
    bad = sorted({hex(ord(c)) for c in msg if not " " <= c <= "~"})
    assert not bad, f"non-printable or non-ASCII characters {bad} in {msg!r}"


# ─────────────────────────── 1. English is unchanged ───────────────────────────
def test_default_and_explicit_en_unchanged(personas):  # noqa: F811
    for member_id in PERSONA_IDS:
        member, status, _ = personas[member_id]
        default = sms_reminder(member, status)
        assert sms_reminder(member, status, "en") == default, member_id
        assert sms_reminder(member, status, lang="en") == default, member_id


# ─────────────────────────── 2. unknown languages ───────────────────────────
@pytest.mark.parametrize("lang", ["fr", "", "EN ", "EN", " es", "pt-BR", None, "None", "none", "null"])
def test_unknown_language_raises(personas, lang):  # noqa: F811
    member, status, _ = personas["SYN-0004"]
    with pytest.raises(ValueError):
        sms_reminder(member, status, lang)


# ─────────────────────────── 3. es / pt rules per persona ───────────────────────────
@pytest.mark.parametrize("lang", I18N_LANGS)
def test_spanish_and_portuguese_rules_for_every_persona(personas, lang):  # noqa: F811
    for member_id in PERSONA_IDS:
        member, status, bundle = personas[member_id]
        msg = sms_reminder(member, status, lang)
        assert_printable_ascii(msg)
        greeting = f"{GREETINGS[lang]} {expected_first_name(member.display_name)},"
        assert msg.startswith(greeting), f"expected {greeting!r}, got {msg!r}"
        assert member.member_id not in msg, msg
        if member.phone_last4 is not None:
            assert member.phone_last4 not in msg, msg
        assert_no_forbidden_words(msg[len(greeting):])
        for f in bundle.findings:
            for secret in (f.condition, f.icd10, f.quote):
                assert secret.lower() not in msg.lower(), f"{secret!r} leaked into {msg!r}"
        assert msg != sms_reminder(member, status), f"{lang} text equals the English text for {member_id}"
        assert sms_reminder(member, status, lang) == msg, "not deterministic"


# ─────────────────────────── 4. Dev, AT_RISK ───────────────────────────
@pytest.mark.parametrize("lang, greeting", [("es", "Hola Dev,"), ("pt", "Ola Dev,")])
def test_dev_at_risk_es_and_pt(personas, lang, greeting):  # noqa: F811
    member, status, _ = personas["SYN-0004"]
    msg = sms_reminder(member, status, lang)
    assert_printable_ascii(msg)
    assert msg.startswith(greeting), msg
    assert "$60.00" in msg, msg
    assert "6 mar 2027" in msg, msg
    for leak in ("SYN-0004", "0404", "MassHealth", "synthetic"):
        assert leak not in msg, f"{leak!r} leaked into {msg!r}"


# ─────────────────────────── 5. properties ───────────────────────────
@settings(max_examples=200, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
@given(name=arbitrary_names, sc=scenarios(), ids=st.tuples(member_ids, member_ids), ph=st.tuples(phones, phones),
       condition=conditions, lang=st.sampled_from(I18N_LANGS))
def test_i18n_properties_hold_for_any_input(name, sc, ids, ph, condition, lang):
    out = []
    for member_id, phone in zip(ids, ph):
        member = build_member(sc, member_id=member_id, display_name=name, phone=phone)
        msg = sms_reminder(member, build_status(sc, member_id=member_id, condition=condition), lang)
        assert_printable_ascii(msg)
        out.append(msg)
    assert out[0] == out[1], "output changed with member_id / phone_last4"
