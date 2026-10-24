# UI extras handoff (branch final/ui-extras)

`app/main.py` was NOT edited. To wire an extra in, add its import next to the other `from app...` imports in
`main.py` and its one-line hook inside the named section of `render_dashboard`. Variables already in scope there:
`member`, `status`, `view`, `llm`, `is_live`, `live`, `wallet_rules` (module level), `data.today`, `section`.

## upload (`app/upload.py`)
- Signature: `def render_upload(member: Member, rules: WalletRules, today: date) -> None:`
- Shows: a multi-file uploader (csv, txt, pdf, png, jpg, jpeg) plus any samples queued by the gallery, turns each
  file into an `EarningsDocument` in memory (`to_document`, caps from `WalletRules`), runs `build_wallet` and shows
  a plain month table (hours, income, meets rule, shortfalls, needs review), or an error naming the file only.
- Import: `from app.upload import render_upload  # noqa: E402`
- Hook, top of `if section == SECTIONS[3]:` (Hours & money): `render_upload(member, wallet_rules, data.today)`
- Mode: CSV works offline; images show `IMAGE_NOTE` and flag the month for review. Text and PDF need live AI;
  in offline mode they are dropped with `LIVE_AI_NOTE`.
- KNOWN GAP: the current file has NO live-AI opt-in checkbox. It calls `choose_llm()` with `demo=None`, so it goes
  live automatically whenever an API key is configured (or `PROOFKIT_DEMO=1` forces offline). The intended
  behavior (explicit checkbox, default offline, text/PDF only with opt-in + key) still needs a test-first change
  in `app/upload.py`, e.g. a checkbox feeding `choose_llm(demo=not opted_in)` with `LLMError` caught.

## samples (`app/samples.py`)
- Signature: `def render_sample_gallery(member_id: str) -> None:`
- Shows: "Sample statements": the member's own fixture statements, a sample PDF, a sample CSV and the red-team
  statement (duplicates listed once). Each row has "Load into upload" (appends to
  `st.session_state[UPLOAD_QUEUE_KEY]`, picked up by `render_upload`) and "Download". All synthetic.
- Import: `from app.samples import render_sample_gallery  # noqa: E402`
- Hook, in `if section == SECTIONS[3]:` right after the upload hook: `render_sample_gallery(member.member_id)`

## sms_card (`app/sms_card.py`)
- Signature: `def render_sms_card(member: Member, status: ProofKitStatus, *, key: str = "ui_extras_sms_lang") -> None:`
- Shows: an EN / ES / PT radio, the SMS from `proofkit.integration.reminder.sms_reminder` via `st.code` (plain,
  printable ASCII, <= 160 chars) and a `len/160` caption. Pure helper: `sms_preview(member, status, lang)`.
- Import: `from app.sms_card import render_sms_card  # noqa: E402`
- Hook, end of `if section == SECTIONS[0]:` (Next steps): `render_sms_card(member, status, key=f"sms-{member.member_id}")`

## metrics (`app/metrics.py`)
- Signature: `def render_metric_tiles(status: ProofKitStatus, today: date, rules: Optional[WalletRules] = None) -> None:`
- Shows: three `st.metric` tiles for the first failing (else first) verification month: hours (`18.00 / 80 h`,
  delta `-62.00 h` or `met`), income (`$520.00 / $580.00`, delta `-$60.00` or `met`) and the proof deadline
  countdown. No wallet shows `n/a`. Pure helper: `metric_tiles(status, today, rules=None) -> list[Tile]`.
- Import: `from app.metrics import render_metric_tiles  # noqa: E402`
- Hook, top of `if section == SECTIONS[3]:` (before the upload hook): `render_metric_tiles(status, data.today, wallet_rules)`

## Notes
- Uploads stay in memory: bytes go straight into an `EarningsDocument`, nothing is written to disk, and the
  filename is a display-only basename (<= 255 chars), never a path.
- None of the extras use `unsafe_allow_html` with user text or import `app.main`.
- `sms_card.py` imports `proofkit.integration.reminder` and `upload.py` imports `proofkit.integration.demo`
  (FINAL's own modules, not re-exported from `proofkit.integration.__init__`).
