# Requirements: sms-reminder

## Introduction
`sms_reminder(member: Member, status: ProofKitStatus) -> str` turns a member's ProofKit status into one SMS.
It must fit one GSM-7 segment, reveal nothing beyond the first name, and be fully deterministic.

## Glossary
- **First name**: one trailing parenthesised suffix is removed from `display_name`, the first whitespace-separated
  token is taken, NFKD-normalised, filtered to printable non-space ASCII (0x21-0x7E), cut to 20 chars; "there" if empty.
- **Body**: the message after the greeting `Hi <first name>,`.
- **Due date**: `status.next_deadline`, else `status.wallet.proof_due_date`, else unknown.
- **Shortfall month**: the first month in `wallet.verification_months` that is present in `wallet.months` with `qualifies == False`.

## R1 Length
User story: As a member, I want one short text so that it arrives as a single SMS.
- WHEN sms_reminder is called with any valid Member and ProofKitStatus THE SYSTEM SHALL return a non-empty string of at most 160 characters.
Acceptance criteria
1. len(message) <= 160 for every persona and every generated input, including 80-char names and shortfalls up to $9,999,999,999.99.

## R2 Character set
- THE SYSTEM SHALL emit only printable ASCII characters (0x20-0x7E).
Acceptance criteria
1. No character outside 0x20-0x7E, including for names made of emoji, CJK or combining marks. No newlines.

## R3 Greeting
- THE SYSTEM SHALL start every message with `Hi <first name>,`.
- IF the folded first name is empty THEN THE SYSTEM SHALL greet with `Hi there,`.
Acceptance criteria
1. "Maria (synthetic)" -> "Hi Maria,"; "José García" -> "Hi Jose,"; "Ｄｅｖ" -> "Hi Dev,"; "(synthetic)" and "😀 Sam" -> "Hi there,".
2. A first token longer than 20 folded characters is cut to 20.
3. Words after the first token and the parenthesised suffix never change the greeting.

## R4 Privacy
- THE SYSTEM SHALL NOT include member_id, phone_last4, any other part of the display name, condition names, ICD-10 codes, the exemption type, program names (MassHealth, Medicaid) or any quote from notes or documents.
- WHEN only member_id, phone_last4, the words after the first name, the parenthesised suffix, exemption type, rationale, review reasons, statement draft or action item text change THE SYSTEM SHALL return an identical message.
Acceptance criteria
1. Dev's message contains none of "SYN-0004", "0404", "MassHealth", "synthetic".
2. No persona message contains its golden-finding conditions, codes or quotes.
3. Hypothesis invariance properties hold for 300 examples each.

## R5 Content by status
- WHEN status is PROTECTED THE SYSTEM SHALL say the member is on track, that no action is needed now, and give the next renewal date (wallet.next_renewal_date, else member.renewal_date).
- WHEN status is NEEDS_REVIEW THE SYSTEM SHALL say part of the proof needs a review and to contact their navigator or clinic, by the due date when known.
- WHEN status is AT_RISK and a shortfall month exists THE SYSTEM SHALL state its income shortfall as "$X.XX short", say to send pay stubs or volunteer hours, and give the due date when known.
- IF status is AT_RISK and no shortfall month exists THEN THE SYSTEM SHALL give a generic action without any amount, plus the due date when known.
Acceptance criteria
1. Dev (SYN-0004): contains "Hi Dev", "$60.00 short", "Mar 6, 2027". SYN-0005: "$170.00 short".
2. A next_deadline of 2027-03-04 replaces the wallet's 2027-03-06.
3. Failing months outside verification_months are ignored. Missing verification months are skipped.
4. PROTECTED bodies contain neither "$" nor "short".

## R6 Determinism
- THE SYSTEM SHALL compute the message only from its arguments: no clock, randomness, environment, logging, network or file I/O.
Acceptance criteria
1. Repeated calls and calls on re-validated copies return equal strings.
2. The module imports none of random, secrets, time, os, io, pathlib, socket, logging, proofkit.common and calls none of today/now/open/print/getenv.

## R7 Formatting
- THE SYSTEM SHALL format dates as "Mon D, YYYY" (e.g. "Mar 6, 2027") without zero-padding or locale dependence.
- THE SYSTEM SHALL format money as "$" + digits + "." + exactly two decimals.
- THE SYSTEM SHALL NOT emit emoji.
Acceptance criteria
1. No ISO dates, numeric slash dates or zero-padded days in the body. Every "$" is followed by \d+\.\d{2}.
