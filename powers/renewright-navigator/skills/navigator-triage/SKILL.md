---
name: navigator-triage
description: Triage RenewRight members for a navigator. Finds at-risk members, pulls each one's status, deadline and what is missing, and shows the drafted SMS reminder. Read-only, synthetic data, never decides eligibility.
---

# Navigator triage

Use only the `renewright` MCP tools. Report what they return, word for word where possible. Use first names only and never invent data.

1. Call `triage` with no arguments.
2. For each member the triage marks `at_risk`, call `member_status` with their `member_id` (format `SYN-####`), then `sms_reminder` with the same `member_id`.
3. Present a table with one row per at-risk member:

   | First name | Status | Deadline | What is missing |
   |---|---|---|---|

   Take the status, proof due date and shortfall (for example "$60 short in Feb 2027") from `member_status`. Below the table, show each member's drafted SMS exactly as `sms_reminder` returned it.
4. End with this disclaimer:

   > RenewRight helps people gather and organize evidence. It does not make eligibility determinations; MassHealth does.

5. Never decide eligibility. Don't say or imply that a member is or isn't eligible, will or won't keep coverage, or qualifies for an exemption beyond what the tools report. If a tool fails or a field is missing, say so and don't fill the gap.
