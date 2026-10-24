---
inclusion: fileMatch
fileMatchPattern: "{src/proofkit/integration/**,app/**,tests/integration/**}"
---
# FINAL: integration and UI rules

## Scope
- Work on `final/<name>` branches after CP2. Edit only `src/proofkit/integration/**`, `app/**` and `tests/integration/**`.
- Use public module APIs only:
  - `from proofkit.extraction import extract_findings`
  - `from proofkit.reasoning import decide_exemption, draft_statement, load_frailty_rules`
  - `from proofkit.wallet import build_wallet, load_wallet_rules`
  - plus `proofkit.contracts` and `proofkit.common`.
  Never import submodules such as `proofkit.wallet.qualify`. If a module is wrong, its owner fixes it test-first on their branch.
- Pass rule file paths through. Don't build `FrailtyRules` or `WalletRules` yourself.
- `build_wallet` raises `ValueError` for a bad upload. Catch it and show which `doc_id` was rejected, never its contents.

## build_status: the 4 status rules, in order (test-first in tests/integration/test_status_rules.py)
1. `exemption.outcome == EXEMPT` -> PROTECTED, `protected_by = "exemption:<type>"`, with the statement draft attached.
2. Else, every `wallet.verification_months` month is present in `wallet.months` and qualifies -> PROTECTED, `protected_by = "compliance:<basis>"`. A member with no documents has `months == []`, so this rule must NOT pass vacuously.
3. Else, exemption NEEDS_CLINICIAN_REVIEW, or any verification month `needs_review` -> NEEDS_REVIEW, with an action item for a clinician review or a re-upload.
4. Else AT_RISK. Action items: the shortfall in plain words ("$60 short in Feb 2027"); the options (add a pay statement, log volunteer hours, ask a clinician about an exemption); `next_deadline = proof_due_date`.
- `exemption` and `wallet` may each be `None`. Test every rule, the empty-wallet case and all 5 personas.

## Escaping
- Run `html.escape` on every note text, quote, `source_quote`, platform, condition, statement and name before it reaches HTML, in both the packet and the app.
- To highlight `quote_start:quote_end`, escape the before, quote and after slices separately, then wrap only the escaped quote in `<mark>`.
- Never use `unsafe_allow_html=True` with user content. Show raw text with `st.text` / `st.code`, or escape it first.
- Test that an injected `<script>` in a note or document comes out as `<script>` in the packet and the app.

## Disclaimer
- Every Streamlit page and every proof packet shows: "ProofKit helps people gather and organize evidence. It does not make eligibility determinations; MassHealth does."
- Test that the packet HTML contains it.

## SMS reminder
- Length and charset: at most 160 characters, every character printable ASCII (0x20-0x7E). No newlines, tabs or other control characters.
- Greeting: the member's first name only: the first word of `display_name`, ignoring a trailing `(...)` suffix, folded to ASCII (NFKD, drop non-ASCII) and cut to 20 characters. Use it only if it then looks like a name: it matches `^[A-Za-z][A-Za-z'-]*$` (letters, with apostrophes or hyphens after the first letter) and is not a program name (MassHealth, Medicaid). Otherwise use the literal fallback `there` ("Hi there").
- Content allowed: the greeting, the status in plain words, the next action, and the deadline (`next_deadline` / `proof_due_date`).
- Income shortfall (product decision, Karthik): for AT_RISK members only, the SMS may include the dollar income shortfall, formatted from the `Decimal` as `$` plus two decimals, rounded half-up (for example "$60.00 short"). It is not health information. PROTECTED and NEEDS_REVIEW messages never include a dollar amount.
- Never include: a condition, an ICD-10 code, an exemption type, a program name (such as MassHealth or Medicaid), the member_id, any phone digits, a last name, or any note or document text (quotes, `source_quote`, platforms). No other income figures (gross income, monthly totals) and no hours.
- Tests: names at the boundaries (José becomes Jose; a 21-character name is cut to 20; empty, `<script>`, digits, `SYN-0004`, phone digits and program names fall back to `there`); all 5 personas stay at most 160 characters and printable ASCII; SYN-0004 contains "$60.00 short"; PROTECTED and NEEDS_REVIEW contain no `$`; no persona's SMS contains its member_id, last name, condition, ICD-10 code, exemption type, "MassHealth" or text from its notes or documents.

## Uploads
- Caps come from `config/wallet_rules.json`. Process files in memory, never written to disk by name.

## Done
- `tests/integration` green, then `make check` fully green on main, a live dry-run on all 5 personas, and a backup recording.
