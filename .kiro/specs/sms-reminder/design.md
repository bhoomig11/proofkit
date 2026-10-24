# Design: sms-reminder

## Location and API
`src/proofkit/integration/reminder.py`, exported from `proofkit.integration`.
Imports allowed: `re`, `unicodedata`, `datetime`, `decimal`, `typing`, `proofkit.contracts`.

```python
def sms_reminder(member: Member, status: ProofKitStatus) -> str
```

## Outline
```python
_MONTHS = ("Jan", ..., "Dec")
_SUFFIX = re.compile(r"\s*\([^()]*\)\s*$")

def _first_name(display_name: str) -> str:            # R3
    tokens = _SUFFIX.sub("", display_name).split()
    if not tokens: return "there"
    folded = "".join(c for c in unicodedata.normalize("NFKD", tokens[0]) if "!" <= c <= "~")
    return folded[:20] or "there"

def _fmt_date(d: date) -> str: return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"   # R7
def _fmt_money(x: Decimal) -> str: return f"${x.quantize(Decimal('0.01')):.2f}"     # R7

def _due(status) -> date | None:                       # R5
    return status.next_deadline or (status.wallet.proof_due_date if status.wallet else None)

def _shortfall(status) -> Decimal | None:              # R5
    # first verification month present in wallet.months with qualifies False -> shortfall_income

def sms_reminder(member, status) -> str:
    greeting = f"Hi {_first_name(member.display_name)},"
    clauses = _clauses(member, status)                 # list[(text, required: bool)]
    return _fit(greeting, clauses)
```

## Clauses per status (required ones marked *)
- PROTECTED: *" you're on track." *" No action needed now." *" Next renewal: {date}." optional " -ProofKit"
- NEEDS_REVIEW: *" Part of your proof needs a review." *" Contact your navigator or clinic" + (" by {due}." | ".")
- AT_RISK with shortfall: *" You're {$X.XX} short for {Mon YYYY}." *" Send pay stubs or volunteer hours" + (" by {due}." | ".") optional " Reply STOP to opt out."
- AT_RISK generic: *" We still need proof of your work hours or income." *" Send pay stubs or volunteer hours" + (" by {due}." | ".")

Only the first name, dates, money and fixed template text ever enter the message. Nothing is read from
exemption, action_items, protected_by, member_id or phone_last4 (R4 by construction).

## Length strategy
1. Build greeting + all clauses.
2. While over 160, drop the last optional clause.
3. If still over 160 (theoretically unreachable: greeting <= 24, longest required set about 135), swap to
   compact fixed variants of required clauses (e.g. "Send stubs/vol hrs by {due}.").
4. Last resort: cut at the last space at or before 160. A word is never split, and the greeting, amount and due date
   always come before any cut point.
A word is never cut while an optional clause remains.

## ASCII safety
All template text is ASCII. Folding is NFKD, then filter to 0x21-0x7E. Dates use a fixed month table, not `strftime`.
A final guard `assert all(" " <= c <= "~" for c in msg)` documents the invariant.

## Correctness properties
| # | Property | Requirement | Test |
|---|---|---|---|
| P1 | len(msg) <= 160 for all inputs | R1 | test_r1_r2_always_hold_for_any_input, test_long_first_name_keeps_required_facts |
| P2 | every char in 0x20-0x7E | R2, R7 | test_r1_r2_always_hold_for_any_input |
| P3 | msg starts with "Hi " + fold(first token) + "," | R3 | test_r3_greeting_is_the_folded_first_name, test_greeting_uses_folded_first_name_only |
| P4 | greeting independent of rest of name and suffix | R3, R4 | test_r3_greeting_ignores_rest_of_name_and_suffix |
| P5 | output invariant under member_id and phone_last4 | R4 | test_r4_member_id_and_phone_do_not_change_output |
| P6 | output invariant under words after the first name | R4 | test_r4_words_after_first_name_do_not_change_output |
| P7 | output invariant under conditions, exemption type, statement, action text | R4 | test_r4_conditions_and_exemption_type_do_not_change_output |
| P8 | body has no ids, program names, exemption types | R4 | test_r4_body_never_names_programs_ids_or_exemption_types, test_persona_message_leaks_nothing |
| P9 | status-specific facts present (on track/renewal; review/navigator/clinic; $X.XX short/pay stubs/volunteer hours; due date) | R5 | test_r5_r7_content_by_status, persona tests |
| P10 | shortfall comes from the first failing verification month | R5 | test_shortfall_comes_from_first_failing_verification_month |
| P11 | f(x) == f(x) == f(copy(x)); no clock/random/I/O imports or calls | R6 | test_r6_same_inputs_same_output, test_reminder_module_is_pure |
| P12 | dates "Mon D, YYYY", money 2 decimals | R7 | assert_formats in every test |

## Security notes
No logging inside the function (the message itself is member-facing data). The function never reads
untrusted note or document text, so injected instructions cannot reach the SMS.
