# UI extras handoff (branch final/ui-extras)

Tests were written first (RED captured in commits e342c9d, 81ce75c and the button test) and `app/main.py` was not edited.

To wire an extra in, add its import next to the other `from app...` imports in `main.py` and its one-line hook in
the named section of `render_dashboard`. In scope there: `member`, `status`, `view`, `llm`, `is_live`, `live`,
`section`, plus module-level `wallet_rules` and `data.today`.

## upload (`app/upload.py`)
- Signature: `def render_upload(member: Member, rules: WalletRules, today: date) -> None:`
- Import: `from app.upload import render_upload  # noqa: E402`
- Hook, top of `if section == SECTIONS[3]:` (Hours & money): `render_upload(member, wallet_rules, data.today)`
- Shows: a multi-file uploader (csv, txt, pdf, png, jpg, jpeg) plus samples queued by the gallery. Each file becomes
  an `EarningsDocument` in memory (`to_document`, caps from `WalletRules`), then `build_wallet` runs and a plain
  month table is shown, or an error that names the file only.
- Offline: CSV is processed offline; images are processed offline too and flagged for review (`IMAGE_NOTE`).
- Live AI: text and PDF need the live AI. NOT YET DONE: the current file still uses an opt-in checkbox
  ("Use live AI to read text and PDF files ...") feeding `upload_llm(live_opt_in)`; there is no
  "Process with live AI" button. `test_live_ai_only_inside_process_button` in `tests/integration/test_ui_extras.py`
  is RED. Without opt-in, text/PDF are dropped with `LIVE_AI_NOTE`.
- Next GREEN step: in `render_upload`, remove the checkbox, process CSV/images with `upload_llm(False)`, and call
  `upload_llm(True)` for text/PDF only inside `if st.button("Process with live AI", ...):`.

## samples (`app/samples.py`)
- Signature: `def render_sample_gallery(member_id: str) -> None:`
- Import: `from app.samples import render_sample_gallery  # noqa: E402`
- Hook, in `if section == SECTIONS[3]:` right after the upload hook: `render_sample_gallery(member.member_id)`
- Shows: the member's own fixture statements, a sample PDF, a sample CSV and the red-team statement (duplicates
  once). Each row has "Load into upload" (appends to `st.session_state[UPLOAD_QUEUE_KEY]` via `queue_sample`, cap 10)
  and "Download". All synthetic.

## sms_card (`app/sms_card.py`)
- Signature: `def render_sms_card(member: Member, status: ProofKitStatus, *, key: str = "ui_extras_sms_lang") -> None:`
- Import: `from app.sms_card import render_sms_card  # noqa: E402`
- Hook, end of `if section == SECTIONS[0]:` (Next steps): `render_sms_card(member, status, key=f"sms-{member.member_id}")`
- Shows: an EN / ES / PT radio, the SMS from `sms_reminder` via `st.code` (printable ASCII, <= 160 chars) and a
  `len/160` caption. Pure helper: `sms_preview(member, status, lang="en") -> tuple[str, str]`.

## metrics (`app/metrics.py`)
- Signature: `def render_metric_tiles(status: ProofKitStatus, today: date, rules: Optional[WalletRules] = None) -> None:`
- Import: `from app.metrics import render_metric_tiles  # noqa: E402`
- Hook, top of `if section == SECTIONS[3]:` (before the upload hook): `render_metric_tiles(status, data.today, wallet_rules)`
- Shows: three `st.metric` tiles for the first failing (else first) verification month: hours (`18.00 / 80 h`,
  `-62.00 h` or `met`), income (`$520.00 / $580.00`, `-$60.00` or `met`) and the proof-deadline countdown. No
  wallet shows `n/a`. Pure helper: `metric_tiles(status, today, rules=None) -> list[Tile]`.

## Notes
- Uploads stay in memory; the filename is a display-only basename (<= 255 chars), never a path.
- No extra uses `unsafe_allow_html` with user text or imports `app.main`.
- `sms_card.py` imports `proofkit.integration.reminder` and `upload.py` imports `proofkit.integration.demo`
  (FINAL's own modules, not re-exported from `proofkit.integration.__init__`).
