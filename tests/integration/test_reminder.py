"""
FINAL RED: sms_reminder(member, status) -> str, example-based.

Each demo persona gets a ProofKitStatus built directly from contract models and the fixtures
(members, expected statuses, expected wallet months, expected decisions, golden findings).
Requirements R1-R7 live in .kiro/specs/sms-reminder/requirements.md.

The helpers at the top (fmt_date, expected_first_name, assert_sms_shape, ...) are the test oracle
and are reused by test_reminder_properties.py.
"""
from __future__ import annotations

import ast
import re
import unicodedata
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from proofkit.contracts import (
    ActionItem,
    ComplianceBasis,
    DecisionOutcome,
    ExemptionDecision,
    ExemptionType,
    FindingsBundle,
    MatchedRule,
    Member,
    MonthlyCompliance,
    OverallStatus,
    ProofKitStatus,
    WalletResult,
)
from proofkit.integration.reminder import sms_reminder

# ─────────────────────────── oracle ───────────────────────────
SMS_LIMIT = 160
FIRST_NAME_MAX = 20
FALLBACK_NAME = "there"
MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
HOURS_REQUIRED = Decimal("80.00")
INCOME_REQUIRED = Decimal("580.00")
PROOF_BUFFER = timedelta(days=14)
CENT = Decimal("0.01")
RULES_VERSION = "test-seed"

# Words that must never reach the SMS body, whatever the inputs (R4). Compared case-insensitively.
FORBIDDEN_WORDS = ("synthetic", "masshealth", "medicaid", "syn-", "medically", "frail",
                   "substance_use", "disability")

_PAREN_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")
# R3: a first name must look like a name: a letter, then letters, apostrophes or hyphens.
NAME_SHAPE = re.compile(r"[A-Za-z][A-Za-z'-]*")
# R3: program names are never used as a first name (compared case-insensitively).
PROGRAM_NAMES = ("masshealth", "medicaid")


def fmt_date(d: date) -> str:
    """R7: 'Mar 6, 2027' (locale-free, no zero padding)."""
    return f"{MONTH_ABBR[d.month - 1]} {d.day}, {d.year}"


def fmt_money(x: Decimal) -> str:
    """R7: two decimals, e.g. '$60.00'."""
    return f"${x.quantize(CENT):.2f}"


def expected_first_name(display_name: str) -> str:
    """R3 oracle. Order matters:
    1. drop one trailing parenthesised suffix such as ' (synthetic)' from the raw name,
    2. take the first whitespace-separated token (str.split),
    3. NFKD, then drop every non-ASCII character,
    4. cut to 20 characters,
    5. use it only if it fully matches ^[A-Za-z][A-Za-z'-]*$ and is not a program name
       (MassHealth or Medicaid, any case); otherwise 'there'.
    """
    tokens = _PAREN_SUFFIX.sub("", display_name).split()
    if not tokens:
        return FALLBACK_NAME
    folded = "".join(ch for ch in unicodedata.normalize("NFKD", tokens[0]) if ch.isascii())[:FIRST_NAME_MAX]
    if NAME_SHAPE.fullmatch(folded) is None or folded.lower() in PROGRAM_NAMES:
        return FALLBACK_NAME
    return folded


def greeting_for(display_name: str) -> str:
    """R3: every message opens with exactly 'Hi <first>,'."""
    return f"Hi {expected_first_name(display_name)},"


def body_of(msg: str, display_name: str) -> str:
    """The message after the greeting. Content checks run on the body so a first name such as
    'Shortt' or 'Review' cannot make a check pass or fail by accident."""
    greeting = greeting_for(display_name)
    assert msg.startswith(greeting), f"expected greeting {greeting!r}, got {msg!r}"
    return msg[len(greeting):]


def assert_formats(body: str) -> None:
    """R7: human dates only, money always with 2 decimals."""
    assert not re.search(r"\d{4}-\d{2}-\d{2}", body), f"ISO date in {body!r}"
    assert not re.search(r"\d{1,2}/\d{1,2}", body), f"numeric date in {body!r}"
    assert not re.search(r"\b(?:%s) 0\d" % "|".join(MONTH_ABBR), body), f"zero-padded day in {body!r}"
    for m in re.finditer(r"\$", body):
        assert re.match(r"\$\d+\.\d{2}(?!\d)", body[m.start():]), f"money without 2 decimals in {body!r}"


def assert_sms_shape(msg: object, member: Member) -> str:
    """R1 + R2 + R3 + R7 on any message. Returns the body."""
    assert isinstance(msg, str)
    assert 0 < len(msg) <= SMS_LIMIT, f"{len(msg)} chars: {msg!r}"
    bad = sorted({hex(ord(c)) for c in msg if not " " <= c <= "~"})
    assert not bad, f"non-printable or non-ASCII characters {bad} in {msg!r}"
    body = body_of(msg, member.display_name)
    assert_formats(body)
    return body


def assert_no_forbidden_words(body: str) -> None:
    low = body.lower()
    for word in FORBIDDEN_WORDS:
        assert word not in low, f"{word!r} leaked into {body!r}"


def due_date_of(status: ProofKitStatus) -> date | None:
    """R5: status.next_deadline, else wallet.proof_due_date, else unknown."""
    if status.next_deadline is not None:
        return status.next_deadline
    return status.wallet.proof_due_date if status.wallet else None


def renewal_date_of(member: Member, status: ProofKitStatus) -> date:
    return status.wallet.next_renewal_date if status.wallet else member.renewal_date


def first_shortfall_of(status: ProofKitStatus) -> Decimal | None:
    """R5: income shortfall of the first verification month that is present and does not qualify."""
    if status.wallet is None:
        return None
    by_month = {m.month: m for m in status.wallet.months}
    for month in status.wallet.verification_months:
        mc = by_month.get(month)
        if mc is not None and not mc.qualifies:
            return mc.shortfall_income
    return None


def assert_content(msg: str, member: Member, status: ProofKitStatus) -> str:
    """R5 content rules by status (on top of the shape rules)."""
    body = assert_sms_shape(msg, member)
    low = body.lower()
    if status.status == OverallStatus.PROTECTED:
        assert "on track" in low, body
        assert "no action" in low, body
        assert fmt_date(renewal_date_of(member, status)) in body, body
        assert "$" not in body and "short" not in low, body
    elif status.status == OverallStatus.NEEDS_REVIEW:
        assert "review" in low, body
        assert "navigator" in low and "clinic" in low, body
    else:
        shortfall = first_shortfall_of(status)
        if shortfall is None:
            assert "$" not in body, f"no month data, so no amount expected: {body!r}"
        else:
            assert f"{fmt_money(shortfall)} short" in body, body
            assert "pay stub" in low and "volunteer hours" in low, body
    if status.status != OverallStatus.PROTECTED:
        due = due_date_of(status)
        if due is not None:
            assert fmt_date(due) in body, body
    return body


# ─────────────────────────── builders (contract models only) ───────────────────────────
def month_from_expected(month: str, exp: dict) -> MonthlyCompliance:
    hours = Decimal(exp["total_hours"]).quantize(CENT)
    income = Decimal(exp["total_income"]).quantize(CENT)
    qualifies = bool(exp["qualifies"])
    if qualifies:
        shortfall_income = shortfall_hours = Decimal("0.00")
    else:
        shortfall_income = Decimal(exp.get("shortfall_income", max(INCOME_REQUIRED - income, Decimal("0")))).quantize(CENT)
        shortfall_hours = max(HOURS_REQUIRED - hours, Decimal("0")).quantize(CENT)
    return MonthlyCompliance(
        month=month,
        total_hours=hours,
        hours_known_for_all_records=exp.get("hours_known_for_all_records", True),
        total_income=income,
        qualifies=qualifies,
        basis=ComplianceBasis(exp["basis"]),
        shortfall_hours=shortfall_hours,
        shortfall_income=shortfall_income,
        record_ids=[],
    )


def wallet_from_expected(member: Member, expected_wallet: dict) -> WalletResult:
    renewal = member.renewal_date.isoformat()
    due = date.fromisoformat(expected_wallet[f"proof_due_date_for_renewal_{renewal}"])
    assert due == member.renewal_date - PROOF_BUFFER
    months = [month_from_expected(k, v) for k, v in sorted(expected_wallet.get(member.member_id, {}).items())]
    return WalletResult(
        member_id=member.member_id,
        records=[],
        months=months,
        verification_months=list(expected_wallet[f"verification_months_for_renewal_{renewal}"]),
        next_renewal_date=member.renewal_date,
        proof_due_date=due,
        rules_version=RULES_VERSION,
    )


def phi_text(member: Member, bundle: FindingsBundle) -> str:
    """Everything sensitive about the member in one string: conditions, codes and note quotes."""
    parts = [f'{f.condition} ({f.icd10}): "{f.quote}"' for f in bundle.findings]
    return f"{member.display_name} {member.member_id} MassHealth/Medicaid. " + "; ".join(parts)


def exemption_from_expected(member: Member, expected_decisions: dict, bundle: FindingsBundle) -> ExemptionDecision:
    exp = expected_decisions["expected"][member.member_id]
    outcome = DecisionOutcome(exp["outcome"])
    sensitive = phi_text(member, bundle)
    exempt = outcome == DecisionOutcome.EXEMPT
    return ExemptionDecision(
        member_id=member.member_id,
        outcome=outcome,
        exemption_type=ExemptionType(exp["exemption_type"]),
        confidence=0.95 if exempt else 0.0,
        matched_rules=[MatchedRule(rule_id=r, category="serious_complex_medical",
                                   finding_ids=list(exp["evidence_finding_ids"]), rationale=sensitive[:500])
                       for r in exp["rule_ids"]],
        evidence_finding_ids=list(exp["evidence_finding_ids"]),
        lookback_months=expected_decisions["lookback_months"],
        as_of=date.fromisoformat(expected_decisions["as_of"]),
        rules_version=RULES_VERSION,
        review_reasons=[sensitive[:300]],
        statement_draft=f"Statement for MassHealth: {sensitive}"[:5000] if exempt else None,
    )


def status_for(member: Member, exp_status: dict, wallet: WalletResult, exemption: ExemptionDecision) -> ProofKitStatus:
    overall = OverallStatus(exp_status["status"])
    action_items: list[ActionItem] = []
    next_deadline = None
    if overall == OverallStatus.AT_RISK:
        next_deadline = wallet.proof_due_date
        failing = [m for m in wallet.months if m.month in wallet.verification_months and not m.qualifies]
        for m in failing:
            action_items.append(ActionItem(priority=1, title=f"${m.shortfall_income} short in {m.month}",
                                           detail="Add a pay statement, log volunteer hours, or ask a clinician "
                                                  "about an exemption.", due=next_deadline))
    return ProofKitStatus(
        member_id=member.member_id,
        status=overall,
        protected_by=exp_status["protected_by"],
        exemption=exemption,
        wallet=wallet,
        next_deadline=next_deadline,
        action_items=action_items,
    )


PERSONA_IDS = ["SYN-0001", "SYN-0002", "SYN-0003", "SYN-0004", "SYN-0005"]


@pytest.fixture
def personas(members, expected_status, expected_wallet, expected_decisions, golden_findings):
    """member_id -> (Member, ProofKitStatus, FindingsBundle), built only from contract models and fixtures."""
    out = {}
    for member_id in PERSONA_IDS:
        member = members[member_id]
        bundle = golden_findings[member_id]
        wallet = wallet_from_expected(member, expected_wallet)
        exemption = exemption_from_expected(member, expected_decisions, bundle)
        out[member_id] = (member, status_for(member, expected_status[member_id], wallet, exemption), bundle)
    return out


def _with_status(base: ProofKitStatus, **update) -> ProofKitStatus:
    """Rebuild through the constructor so every contract validator runs again."""
    return ProofKitStatus.model_validate({**base.model_dump(), **update})


def _month(month: str, *, qualifies: bool, shortfall: str = "0.00", needs_review: bool = False) -> MonthlyCompliance:
    short = Decimal(shortfall)
    return MonthlyCompliance(
        month=month, total_hours=Decimal("10.00"), hours_known_for_all_records=True,
        total_income=(INCOME_REQUIRED - short if not qualifies else Decimal("600.00")),
        qualifies=qualifies, basis=ComplianceBasis.INCOME if qualifies else ComplianceBasis.NONE,
        shortfall_hours=Decimal("0.00") if qualifies else Decimal("70.00"), shortfall_income=short,
        record_ids=[], needs_review=needs_review, review_reasons=["low confidence"] if needs_review else [],
    )


# ─────────────────────────── personas: R1-R7 ───────────────────────────
@pytest.mark.parametrize("member_id", PERSONA_IDS)
def test_persona_message_shape(personas, member_id):
    """R1 length, R2 ASCII, R3 greeting, R7 formats."""
    member, status, _ = personas[member_id]
    assert_sms_shape(sms_reminder(member, status), member)


@pytest.mark.parametrize("member_id", PERSONA_IDS)
def test_persona_message_content(personas, member_id):
    """R5: content matches the persona's status."""
    member, status, _ = personas[member_id]
    assert_content(sms_reminder(member, status), member, status)


@pytest.mark.parametrize("member_id", PERSONA_IDS)
def test_persona_message_leaks_nothing(personas, member_id):
    """R4: no ids, phone digits, name suffix, program names, exemption type, conditions, codes or quotes."""
    member, status, bundle = personas[member_id]
    msg = sms_reminder(member, status)
    body = body_of(msg, member.display_name)
    assert member.member_id not in msg
    assert member.phone_last4 not in msg
    assert_no_forbidden_words(body)
    if status.exemption is not None:
        assert status.exemption.exemption_type.value not in body.lower()
        assert status.exemption.exemption_type.value.replace("_", " ") not in body.lower()
    for f in bundle.findings:
        for secret in (f.condition, f.icd10, f.quote):
            assert secret.lower() not in msg.lower(), f"{secret!r} leaked into {msg!r}"


@pytest.mark.parametrize("member_id", PERSONA_IDS)
def test_persona_message_is_deterministic(personas, member_id):
    """R6: same inputs, same output; a rebuilt copy of the inputs gives the same output too."""
    member, status, _ = personas[member_id]
    first = sms_reminder(member, status)
    assert sms_reminder(member, status) == first
    again = sms_reminder(Member.model_validate(member.model_dump()), ProofKitStatus.model_validate(status.model_dump()))
    assert again == first


@pytest.mark.parametrize("member_id, renewal", [("SYN-0001", "Mar 20, 2027"), ("SYN-0002", "Mar 20, 2027"),
                                                ("SYN-0003", "Mar 20, 2027")])
def test_protected_personas_get_on_track_and_renewal_date(personas, member_id, renewal):
    member, status, _ = personas[member_id]
    assert status.status == OverallStatus.PROTECTED
    msg = sms_reminder(member, status)
    body = body_of(msg, member.display_name)
    assert renewal in body
    assert "on track" in body.lower() and "no action" in body.lower()


def test_dev_message(personas):
    """SYN-0004 'Dev': AT_RISK, Feb 2027 income $520.00 -> $60.00 short, proof due Mar 6, 2027 (2027-03-20 - 14 d)."""
    member, status, _ = personas["SYN-0004"]
    assert status.status == OverallStatus.AT_RISK
    assert status.next_deadline == date(2027, 3, 6)
    msg = sms_reminder(member, status)
    assert_content(msg, member, status)
    assert msg.startswith("Hi Dev,")
    assert "Hi Dev" in msg
    assert "$60.00 short" in msg
    assert "Mar 6, 2027" in msg
    for leak in ("SYN-0004", "0404", "MassHealth", "synthetic"):
        assert leak not in msg, f"{leak!r} leaked into {msg!r}"


def test_adversarial_persona_is_170_short(personas):
    member, status, _ = personas["SYN-0005"]
    msg = sms_reminder(member, status)
    assert msg.startswith("Hi Adversarial,")
    assert "$170.00 short" in msg
    assert "Mar 6, 2027" in msg


# ─────────────────────────── R5: due date and month selection ───────────────────────────
def test_due_date_prefers_status_next_deadline(personas):
    member, status, _ = personas["SYN-0004"]
    msg = sms_reminder(member, _with_status(status, next_deadline=date(2027, 3, 4)))
    body = assert_sms_shape(msg, member)
    assert "Mar 4, 2027" in body
    assert "Mar 6, 2027" not in body


def test_due_date_falls_back_to_wallet_proof_due_date(personas):
    member, status, _ = personas["SYN-0004"]
    msg = sms_reminder(member, _with_status(status, next_deadline=None))
    body = assert_sms_shape(msg, member)
    assert "Mar 6, 2027" in body
    assert "$60.00 short" in body


def test_at_risk_without_wallet_gives_generic_action_and_deadline(personas):
    member, status, _ = personas["SYN-0004"]
    st = _with_status(status, wallet=None, next_deadline=date(2027, 3, 6))
    body = assert_content(sms_reminder(member, st), member, st)
    assert "Mar 6, 2027" in body
    assert "$" not in body


def test_at_risk_without_wallet_or_deadline_still_valid(personas):
    member, status, _ = personas["SYN-0004"]
    st = _with_status(status, wallet=None, next_deadline=None, action_items=[])
    body = assert_content(sms_reminder(member, st), member, st)
    assert "$" not in body


def test_at_risk_with_empty_wallet_months_gives_generic_action(personas):
    """SYN-0003's wallet has no months at all (no documents)."""
    member, status, _ = personas["SYN-0004"]
    empty_wallet = personas["SYN-0003"][1].wallet.model_dump()
    empty_wallet["member_id"] = member.member_id
    assert empty_wallet["months"] == []
    st = _with_status(status, wallet=empty_wallet, next_deadline=None)
    body = assert_content(sms_reminder(member, st), member, st)
    assert "Mar 6, 2027" in body
    assert "$" not in body


@pytest.mark.parametrize("months, verification, expected, absent", [
    # Jan qualifies, Feb is short: Feb's amount.
    ([("2027-01", True, "0.00"), ("2027-02", False, "60.00")], ["2027-01", "2027-02"], "$60.00", []),
    # both short: the FIRST verification month wins.
    ([("2027-01", False, "100.00"), ("2027-02", False, "60.00")], ["2027-01", "2027-02"], "$100.00", ["$60.00"]),
    # a failing month outside the verification window is ignored.
    ([("2026-12", False, "300.00"), ("2027-02", False, "60.00")], ["2027-02"], "$60.00", ["$300.00"]),
    # a verification month with no data is skipped, not treated as $580 short.
    ([("2027-02", False, "12.34")], ["2027-01", "2027-02"], "$12.34", ["$580.00"]),
])
def test_shortfall_comes_from_first_failing_verification_month(personas, months, verification, expected, absent):
    member, status, _ = personas["SYN-0004"]
    wallet = status.wallet.model_dump()
    wallet["months"] = [_month(m, qualifies=q, shortfall=s).model_dump() for m, q, s in months]
    wallet["verification_months"] = verification
    st = _with_status(status, wallet=wallet)
    body = assert_content(sms_reminder(member, st), member, st)
    assert f"{expected} short" in body
    for amount in absent:
        assert amount not in body


def test_needs_review_points_to_navigator_or_clinic_by_due_date(personas):
    member, status, _ = personas["SYN-0004"]
    wallet = status.wallet.model_dump()
    wallet["months"] = [_month("2027-02", qualifies=False, shortfall="60.00", needs_review=True).model_dump()]
    st = _with_status(status, status=OverallStatus.NEEDS_REVIEW, wallet=wallet, action_items=[])
    body = assert_content(sms_reminder(member, st), member, st)
    assert "Mar 6, 2027" in body
    assert_no_forbidden_words(body)


def test_needs_review_from_clinician_review_leaks_no_reasons(personas):
    member, status, _ = personas["SYN-0004"]
    exemption = status.exemption.model_dump()
    exemption.update(outcome=DecisionOutcome.NEEDS_CLINICIAN_REVIEW, exemption_type=ExemptionType.NONE,
                     review_reasons=["Possible mild intermittent asthma (J45.20) needs a clinician"])
    st = _with_status(status, status=OverallStatus.NEEDS_REVIEW, exemption=exemption, action_items=[])
    msg = sms_reminder(member, st)
    body = assert_content(msg, member, st)
    for secret in ("asthma", "J45.20"):
        assert secret.lower() not in body.lower()


# ─────────────────────────── R3: greeting ───────────────────────────
@pytest.mark.parametrize("display_name, first", [
    ("Maria (synthetic)", "Maria"),
    ("Dev Patel (synthetic)", "Dev"),
    ("José García", "Jose"),
    ("Zoë", "Zoe"),
    ("Ｄｅｖ", "Dev"),                                        # fullwidth folds under NFKD
    ("  Ana   Lucia  ", "Ana"),
    ("Dev(synthetic)", "Dev"),
    ("(synthetic)", "there"),
    ("😀 Sam", "there"),                                      # first token folds to nothing
    ("李", "there"),
    ("Bartholomew-Alexander-Fitzgerald Smith", "Bartholomew-Alexande"),
    ("Abcdefghijklmnopqrstuvwxy Smith", "Abcdefghijklmnopqrst"),   # 25 letters -> 20
    ("x" * 80, "x" * 20),
    ("O'Neil Smith", "O'Neil"),                               # apostrophe after the first letter is fine
    ("Mary-Jane Watson", "Mary-Jane"),                        # hyphen after the first letter is fine
    # tokens that do not look like a name fall back to 'there'
    ("SYN-0004 Patel", "there"),
    ("0404", "there"),
    ("Dev2 Patel", "there"),
    ("-Dev Patel", "there"),
    ("'Dev Patel", "there"),
    ("Dev. Patel", "there"),
    ("$1.00 Dev", "there"),
    ("Patel, Dev", "there"),
    ("MassHealth Dev", "there"),
    ("MEDICAID Dev", "there"),
])
def test_greeting_uses_folded_first_name_only(personas, display_name, first):
    assert expected_first_name(display_name) == first           # guards the oracle itself
    _, status, _ = personas["SYN-0004"]
    member = Member(member_id="SYN-0004", display_name=display_name, renewal_date=date(2027, 3, 20),
                    phone_last4="0404")
    msg = sms_reminder(member, status)
    assert_sms_shape(msg, member)
    assert msg.startswith(f"Hi {first},")


HOSTILE_LEAKS = ("SYN-0004", "0404", "M32", "Patel", "REPLY", "<script>")
HOSTILE_LEAKS_ANY_CASE = ("masshealth", "medicaid")


@pytest.mark.parametrize("display_name", [
    "SYN-0004 Patel",
    "0404 Patel",
    "M32.14 Dev",
    "MassHealth Dev",
    "medicaid Dev",
    "Patel, Dev",
    "Dev,REPLY-YES Smith",
    "<script> Dev",
    "123",
])
def test_hostile_first_token_falls_back_to_there(personas, display_name):
    """R3 + R4 on the WHOLE message: a first token that is not a name never reaches the SMS."""
    assert expected_first_name(display_name) == FALLBACK_NAME   # guards the oracle itself
    _, status, _ = personas["SYN-0004"]
    member = Member(member_id="SYN-0004", display_name=display_name, renewal_date=date(2027, 3, 20),
                    phone_last4="0404")
    msg = sms_reminder(member, status)
    assert_sms_shape(msg, member)
    assert msg.startswith("Hi there,"), msg
    for leak in HOSTILE_LEAKS:
        assert leak not in msg, f"{leak!r} leaked into {msg!r}"
    for leak in HOSTILE_LEAKS_ANY_CASE:
        assert leak not in msg.lower(), f"{leak!r} leaked into {msg!r}"


def test_long_first_name_keeps_required_facts(personas):
    """R1 under the worst case: a 20-char name, the largest realistic shortfall and a long date."""
    _, status, _ = personas["SYN-0004"]
    member = Member(member_id="SYN-0004", display_name="W" * 80, renewal_date=date(2027, 10, 14),
                    phone_last4="0404")
    wallet = status.wallet.model_dump()
    wallet["months"] = [_month("2027-09", qualifies=False, shortfall="580.00").model_dump()]
    wallet["verification_months"] = ["2027-09"]
    wallet.update(next_renewal_date=date(2027, 10, 14), proof_due_date=date(2027, 9, 30))
    st = _with_status(status, wallet=wallet, next_deadline=date(2027, 9, 30))
    body = assert_content(sms_reminder(member, st), member, st)
    assert "$580.00 short" in body and "Sep 30, 2027" in body


# ─────────────────────────── R4: invariance ───────────────────────────
def test_output_ignores_ids_phone_rest_of_name_and_conditions(personas):
    member, status, _ = personas["SYN-0004"]
    base = sms_reminder(member, status)
    other_member = Member(member_id="SYN-0099", display_name="Dev Quincy Public (synthetic)",
                          renewal_date=member.renewal_date, phone_last4="9999")
    exemption = status.exemption.model_dump()
    exemption.update(member_id="SYN-0099", review_reasons=["Systemic lupus erythematosus (M32.14)"])
    wallet = status.wallet.model_dump()
    wallet["member_id"] = "SYN-0099"
    other_status = _with_status(status, member_id="SYN-0099", exemption=exemption, wallet=wallet)
    assert sms_reminder(other_member, other_status) == base


def test_exempt_output_ignores_exemption_type_and_statement(personas):
    member, status, _ = personas["SYN-0001"]
    base = sms_reminder(member, status)
    exemption = status.exemption.model_dump()
    exemption.update(exemption_type=ExemptionType.SUBSTANCE_USE_TREATMENT,
                     statement_draft="Opioid use disorder (F11.20) in treatment, per MassHealth rules.")
    st = _with_status(status, exemption=exemption, protected_by="exemption:substance_use_treatment")
    assert sms_reminder(member, st) == base


# ─────────────────────────── R6: purity ───────────────────────────
BANNED_IMPORT_PREFIXES = ("random", "secrets", "time", "os", "io", "pathlib", "shutil", "socket", "subprocess",
                          "uuid", "requests", "httpx", "urllib", "anthropic", "logging", "proofkit.common")
BANNED_CALLS = {"today", "now", "utcnow", "open", "print", "input", "read_text", "read_bytes", "write_text",
                "write_bytes", "complete_json", "getenv", "urandom", "sleep", "system", "popen", "urlopen"}


def test_reminder_module_is_pure():
    """R6: no clock, no randomness, no I/O (static check, same approach as tests/unit/wallet/test_purity.py)."""
    import proofkit.integration.reminder as reminder

    tree = ast.parse(Path(reminder.__file__).read_text(encoding="utf-8"))
    imports = {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imports |= {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    banned = {i for i in imports if any(i == p or i.startswith(p + ".") for p in BANNED_IMPORT_PREFIXES)}
    assert not banned, banned
    calls = {getattr(n.func, "attr", getattr(n.func, "id", None)) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not calls & BANNED_CALLS, calls & BANNED_CALLS


# ─────────────────────────── security review: id binding and decimal context ───────────────────────────
def _sms_fragments(msg: str) -> list[str]:
    """The would-be SMS split into its greeting and sentence fragments (anything 6+ chars is checked)."""
    pieces = re.split(r"(?<=[,.])\s+", msg)
    return [msg] + [p.strip() for p in pieces if len(p.strip()) >= 6]


@pytest.mark.parametrize("case", ["member_vs_status", "wallet_vs_member", "exemption_vs_member"])
def test_member_id_mismatch_raises_before_rendering(personas, case):
    """A status that belongs to someone else must never be rendered for this member.

    For each case, the 'would-be' SMS is rendered from a consistent copy of the same inputs (every id
    rewritten to one value); the ValueError message must not contain any of its text.
    """
    dev, dev_status, _ = personas["SYN-0004"]
    _, james_status, _ = personas["SYN-0002"]

    if case == "member_vs_status":
        status = james_status
        consistent_member = Member.model_validate({**dev.model_dump(), "member_id": "SYN-0002"})
        consistent_status = james_status
    elif case == "wallet_vs_member":
        status = ProofKitStatus.model_validate({**dev_status.model_dump(), "wallet": james_status.wallet.model_dump()})
        consistent_member = dev
        consistent_status = ProofKitStatus.model_validate(
            {**dev_status.model_dump(),
             "wallet": {**james_status.wallet.model_dump(), "member_id": dev.member_id}})
    else:
        status = ProofKitStatus.model_validate(
            {**dev_status.model_dump(), "exemption": james_status.exemption.model_dump()})
        consistent_member = dev
        consistent_status = ProofKitStatus.model_validate(
            {**dev_status.model_dump(),
             "exemption": {**james_status.exemption.model_dump(), "member_id": dev.member_id}})

    would_be = sms_reminder(consistent_member, consistent_status)
    assert would_be.startswith("Hi Dev,")

    with pytest.raises(ValueError) as excinfo:
        sms_reminder(dev, status)
    text = str(excinfo.value)
    for fragment in _sms_fragments(would_be):
        assert fragment not in text, f"would-be SMS text {fragment!r} leaked into the error {text!r}"


def test_output_does_not_depend_on_ambient_decimal_context(personas):
    """R6/R7: money formatting must not depend on the caller's decimal context (precision or rounding)."""
    import decimal

    member, status, _ = personas["SYN-0004"]
    default = sms_reminder(member, status)
    with decimal.localcontext() as ctx:
        ctx.prec = 3
        ctx.rounding = decimal.ROUND_FLOOR
        hostile = sms_reminder(member, status)
    assert hostile == default
    assert "$60.00 short" in default
    assert "$60.00 short" in hostile
