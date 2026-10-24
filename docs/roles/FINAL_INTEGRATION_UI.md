# FINAL: Integration + UI (whole team, last 4–5 hours)

Start only after **CP2**: all three modules are merged to main with acceptance tests green. Work on branches `final/<name>`.

## You own
`src/proofkit/integration/**` · `app/**` · `tests/integration/**`

## You must NOT
Edit module internals. Call only the public APIs in each module's `__init__.py`. If a module is wrong, its owner fixes it on their branch, test-first.

## Split
| Who | Task |
|---|---|
| P1B | `build_status` rules (test-first in `tests/integration/test_status_rules.py`), `run_member`, get `test_end_to_end.py` green |
| P2 | Proof packet: escaped HTML with the monthly table, highlighted evidence quotes, statement, deadlines, disclaimer → PDF optional. Reminder text (≤ 160 chars, no PHI beyond the first name). |
| P1A | Streamlit app: persona picker, upload, status card, evidence viewer (highlight `quote_start:quote_end` in the note), packet download, red-team toggle that shows the injected text being ignored |

## Status rules (implement test-first)
1. `exemption.outcome == EXEMPT` → PROTECTED, `protected_by = "exemption:<type>"`, attach the statement draft.
2. Else, all `wallet.verification_months` present and qualifying → PROTECTED, `protected_by = "compliance:<basis>"`.
3. Else, exemption NEEDS_CLINICIAN_REVIEW or any verification month `needs_review` → NEEDS_REVIEW, with an action item to get a clinician review or re-upload.
4. Else AT_RISK, with action items: the shortfall ("$60 short in Feb 2027"), options (add a pay statement, log volunteer hours, ask a clinician about an exemption), `next_deadline = proof_due_date`.

## UI security
- Escape all note and document text (`html.escape`). Never use `unsafe_allow_html` with user content.
- Upload caps come from `wallet_rules.json`. Files are processed in memory, never written to disk by name.
- Show the disclaimer on every page and in the packet.
- Demo data: synthetic personas only.

## Checklist
- [ ] `tests/integration` all green, then `make check` fully green on main
- [ ] Live dry-run with the real LLM on all 5 personas
- [ ] Backup screen recording of the demo
- [ ] Pitch rehearsed twice with the eval slide
