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
- At most 160 characters, printable ASCII only (0x20-0x7E).
- First name only, plus the deadline or next action. Never a last name, member_id, condition, ICD-10 code, income or note text.
- Test long first names and non-ASCII names: truncate or fall back to a generic greeting, never exceed 160.

## Uploads
- Caps come from `config/wallet_rules.json`. Process files in memory, never written to disk by name.

## Done
- `tests/integration` green, then `make check` fully green on main, a live dry-run on all 5 personas, and a backup recording.
