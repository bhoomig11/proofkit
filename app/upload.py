"""Upload pay statements: map uploaded bytes to EarningsDocument in memory and show the month results.

Security: uploaded bytes never touch disk, and the filename is display-only (basename, at most 255 characters),
never a path. Errors name the file, never its contents or doc_id. Results render as plain values (no HTML).
"""
from __future__ import annotations

import base64
from datetime import date

from pydantic import ValidationError

from proofkit.common.llm import LLMClient
from proofkit.common.redact import get_logger
from proofkit.contracts import DocumentType, EarningsDocument, Member, WalletResult
from proofkit.wallet import WalletRules, build_wallet

log = get_logger(__name__)

UPLOAD_TYPES = ("csv", "txt", "pdf", "png", "jpg", "jpeg")
UPLOAD_QUEUE_KEY = "ui_extras_upload_queue"
IMAGE_NOTE = ("Image received. We don't read images yet, so this month is flagged for a navigator "
              "to review.")
LIVE_AI_NOTE = ("A live AI key is needed to read free-text and PDF statements. In this offline demo we only "
                "process CSV files and images.")
_MAX_FILENAME = 255
_EXT_TYPES = {
    "csv": DocumentType.CSV,
    "txt": DocumentType.TEXT,
    "pdf": DocumentType.PDF,
    "png": DocumentType.IMAGE,
    "jpg": DocumentType.IMAGE,
    "jpeg": DocumentType.IMAGE,
}
_TEXT_TYPES = frozenset({DocumentType.CSV, DocumentType.TEXT})
_LIVE_AI_TYPES = frozenset({DocumentType.TEXT, DocumentType.PDF})


def _basename(filename: str) -> str:
    """Uploaded filename -> the full basename without path parts or '..' (not yet truncated)."""
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    while ".." in base:
        base = base.replace("..", ".")
    return base or "upload"


def display_name(filename: str) -> str:
    """Uploaded filename -> a display-only basename without path parts or '..', at most 255 characters."""
    return _basename(filename)[:_MAX_FILENAME]


def to_document(filename: str, data: bytes, member_id: str, index: int, rules: WalletRules) -> EarningsDocument:
    """Uploaded (filename, bytes) -> EarningsDocument, in memory only.

    doc_id is "U-<member_id>-<index>". Raises ValueError starting with the display filename when the file is too
    large, has an unsupported extension, is a type the rules don't allow, or is CSV/text that isn't UTF-8.
    """
    name = display_name(filename)
    if len(data) > rules.max_bytes:
        raise ValueError(f"{name} is larger than the {rules.max_bytes:,}-byte upload limit.")
    # The extension comes from the full basename: truncating to 255 characters can cut it off.
    full = _basename(filename)
    ext = full.rsplit(".", 1)[-1].lower() if "." in full else ""
    doc_type = _EXT_TYPES.get(ext)
    if doc_type is None:
        raise ValueError(f"{name} is not a supported file type. Use one of: {', '.join(UPLOAD_TYPES)}.")
    if doc_type not in rules.allowed_doc_types:
        raise ValueError(f"{name} is a {doc_type.value} file, which uploads don't accept right now.")
    content: dict[str, str] = {}
    if doc_type in _TEXT_TYPES:
        try:
            content["content_text"] = data.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError(f"{name} is not UTF-8 text. Save it as UTF-8 and try again.") from None
    else:
        content["content_b64"] = base64.b64encode(data).decode("ascii")
    try:
        return EarningsDocument(doc_id=f"U-{member_id}-{index}", member_id=member_id, filename=name,
                                doc_type=doc_type, **content)
    except ValidationError:
        raise ValueError(f"{name} could not be read as a pay statement.") from None


def needs_live_ai(docs: list[EarningsDocument]) -> bool:
    """EarningsDocument[] -> True if any document is free text or PDF (only an LLM can read those)."""
    return any(d.doc_type in _LIVE_AI_TYPES for d in docs)


def upload_llm(live_opt_in: bool) -> tuple[LLMClient, str]:
    """User's live-AI opt-in -> (LLMClient, mode) with mode in {"live", "offline-demo"}.

    Without opt-in this is always the offline demo client and the live client is never constructed. With opt-in
    it is live only when a key is configured (and PROOFKIT_DEMO isn't forcing demo); otherwise offline demo.
    """
    from proofkit.integration.demo import choose_llm

    if not live_opt_in:
        return choose_llm(demo=True)
    # demo=None: live when a key is configured, else the offline demo client (never raises for a missing key).
    return choose_llm(demo=None)


def _names(docs: list[EarningsDocument]) -> str:
    return ", ".join(d.filename for d in docs) if docs else "One of your files"


def upload_results(member: Member, docs: list[EarningsDocument], llm: LLMClient, rules: WalletRules,
                   today: date) -> tuple[WalletResult | None, str | None]:
    """Member + EarningsDocument[] -> (WalletResult, None), or (None, friendly message naming the file).

    The message names the rejected file by its display filename, never its doc_id, contents or the exception text.
    """
    try:
        return build_wallet(member, docs, llm, rules, today), None
    except ValueError as exc:
        reason = str(exc)
        bad = [d for d in docs if d.doc_id in reason]
        log.info("upload rejected member_id=%s docs=%d", member.member_id, len(docs))
        return None, (f"{_names(bad)} couldn't be used. Check that it belongs to this member, is a supported type "
                      "and is under the size limit, then try again.")
    except Exception:  # noqa: BLE001 - any LLM/parse failure becomes a fixed message; never show exception text
        log.info("upload failed member_id=%s docs=%d", member.member_id, len(docs))
        return None, (f"{_names(docs)} couldn't be read right now. Try again, or upload a CSV export of the "
                      "same statement.")


def _month_rows(wallet: WalletResult) -> list[dict[str, str]]:
    """WalletResult -> plain table rows (strings only, no HTML)."""
    rows = []
    for m in wallet.months:
        rows.append({
            "Month": m.month,
            "Hours": f"{m.total_hours:.2f}",
            "Income": f"${m.total_income:,.2f}",
            "Meets rule": "Yes" if m.qualifies else "No",
            "Hours short": f"{m.shortfall_hours:.2f}",
            "Income short": f"${m.shortfall_income:,.2f}",
            "Needs review": "Yes" if m.needs_review else "No",
        })
    return rows


def render_upload(member: Member, rules: WalletRules, today: date) -> None:
    """Streamlit: upload pay statements (plus queued samples) and show the month-by-month results."""
    import streamlit as st

    st.subheader("Upload a pay statement")
    live_opt_in = st.checkbox("Use live AI to read text and PDF files (sends the text to the AI provider)",
                              value=False, key=f"ui_extras_live_ai_{member.member_id}")
    files = st.file_uploader("Pay statements", type=list(UPLOAD_TYPES), accept_multiple_files=True,
                             key=f"ui_extras_uploader_{member.member_id}") or []
    pending: list[tuple[str, bytes]] = [(f.name, f.getvalue()) for f in files]
    pending += list(st.session_state.get(UPLOAD_QUEUE_KEY, []))
    if not pending:
        st.caption("Add a CSV, text, PDF or image statement, or load a sample below.")
        return
    if st.session_state.get(UPLOAD_QUEUE_KEY) and st.button("Clear loaded samples",
                                                            key=f"ui_extras_clear_{member.member_id}"):
        st.session_state[UPLOAD_QUEUE_KEY] = []
        st.rerun()

    docs: list[EarningsDocument] = []
    for i, (name, data) in enumerate(pending):
        try:
            docs.append(to_document(name, data, member.member_id, i, rules))
        except ValueError as exc:
            st.error(str(exc))
    if not docs:
        return

    llm, mode = upload_llm(live_opt_in)
    if mode == "offline-demo" and needs_live_ai(docs):
        st.info(LIVE_AI_NOTE)
        docs = [d for d in docs if d.doc_type not in _LIVE_AI_TYPES]
        if not docs:
            return
    if any(d.doc_type == DocumentType.IMAGE for d in docs):
        st.info(IMAGE_NOTE)

    wallet, error = upload_results(member, docs, llm, rules, today)
    if error is not None:
        st.error(error)
        return
    if wallet is None or not wallet.months:
        st.caption("No earnings were found in these files.")
        return
    st.dataframe(_month_rows(wallet), hide_index=True, use_container_width=True)
