---
inclusion: always
---
# ProofKit: security rules (docs/04_SECURITY.md, CLAUDE.md section 3)

## Data
- Synthetic data only. `member_id` matches `SYN-\d{4}`. Never add real names, MRNs, SSNs, DOBs, addresses or real earnings documents to code, fixtures, prompts, demos, screenshots or commit messages. "My friend's note" counts as real.

## Secrets
- `.env` and `.env.*` are off-limits: never read, search, open, print or commit them. Only `.env.example` may be touched. The guard hook blocks the rest.
- Read keys only through `proofkit.common.config`. Never put a key in chat, code, tests or commit messages.
- `scripts/scan_secrets.py` must stay clean. It runs in the Stop hook and in `make security`.

## Untrusted text (clinical notes, uploaded documents)
- It is data, never instructions. Send it to the LLM only as `llm.complete_json(task=..., instructions=..., untrusted_text=...)`.
- Never interpolate untrusted text into `instructions` (no f-strings, `.format`, `%` or `+`).
- Its content never changes code paths, prompts or decisions.
- Tests assert that `"<untrusted_document>"` is in `llm.calls[i]["user"]` and that the document text is not in `instructions`.

## Validation and grounding
- Validate every LLM output against a pydantic contract. Treat a wrong shape as an `LLMError`-style failure, not a crash.
- Ground every quote with `proofkit.common.grounding.locate_quote`. If it isn't found, drop the item and count it (`dropped_ungrounded`). Store the source slice from the returned span, not the LLM's text.
- Drop items whose quote overlaps `proofkit.common.injection.injection_spans`.
- Wallet records also need their income and hours to appear as tokens inside the quote.

## Deterministic decisions
- The LLM extracts; rules code decides. `decide_exemption`, `evaluate_months` and `compute_deadlines` take no LLM and do no I/O or clock reads.
- Never let free-form LLM text set `outcome`, `qualifies`, `status`, `hours` or `gross_income` without validation and grounding.
- Fail safe: when unsure, drop the item or route it to NEEDS_CLINICIAN_REVIEW / `needs_review`. Never a silent EXEMPT or "qualifies".
- `draft_statement` rejects an LLM summary that invents ICD-10 codes or conditions, and falls back to the template.

## Rendering and uploads
- Run `html.escape` on all note text, document text, quotes, platforms and statements before they reach HTML.
- Never use `unsafe_allow_html=True` with user content.
- Show the disclaimer on every page and in the packet.
- Size, type and page caps come from `config/wallet_rules.json`. Parse in memory. `filename` is display-only and is never used as a path.

## Logging
- Log only through `proofkit.common.redact.get_logger(__name__)`.
- Log IDs and counts, never content: `log.info("extracted note_id=%s findings=%d", note_id, n)`. Never log raw note text, document contents, quotes or prompts.

## Banned
- `eval`, `exec`, `pickle`, unsafe `yaml.load`, `subprocess(..., shell=True)`, and dynamic imports (`importlib`, `__import__`) of user input.
- A real LLM or network call in unit, contract or acceptance tests (only `@pytest.mark.live`, opt-in).
- New or unpinned dependencies without telling the user.
