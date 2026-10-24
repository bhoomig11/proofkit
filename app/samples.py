"""Sample statement gallery: synthetic fixtures a user can download or load straight into the uploader.

All samples are synthetic fixture data (SYN-####, made-up platforms). Fixtures are read in memory; nothing is
written to disk.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from app.upload import UPLOAD_QUEUE_KEY

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"
_PDF_FIXTURE = FIXTURES / "wallet" / "D-0002-ridenow-feb-pdf.json"
_REDTEAM_FIXTURE = FIXTURES / "earnings_docs" / "D-0005-qd-feb.json"
_MIME = {"csv": "text/csv", "txt": "text/plain", "pdf": "application/pdf", "png": "image/png",
         "jpg": "image/jpeg", "jpeg": "image/jpeg"}
_SAMPLE_CSV = (b"platform,period_start,period_end,hours,gross_pay\n"
               b"quickdash,2027-02-01,2027-02-28,85,700.00\n")


@dataclass(frozen=True)
class SampleDoc:
    """One downloadable sample statement: a label, a display filename, its MIME type and its bytes."""

    label: str
    filename: str
    mime: str
    data: bytes


def _mime(filename: str) -> str:
    return _MIME.get(filename.rsplit(".", 1)[-1].lower(), "application/octet-stream")


def _fixture_sample(path: Path, label: str) -> SampleDoc:
    """EarningsDocument fixture JSON -> SampleDoc with its exact bytes (text as UTF-8, binary decoded)."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    if doc.get("content_text") is not None:
        data = doc["content_text"].encode("utf-8")
    else:
        data = base64.b64decode(doc["content_b64"])
    filename = str(doc["filename"]).replace("\\", "/").rsplit("/", 1)[-1]
    return SampleDoc(label=label, filename=filename, mime=_mime(filename), data=data)


def sample_documents(member_id: str) -> list[SampleDoc]:
    """member_id -> SampleDoc[]: the member's own fixture statements, a sample PDF, a sample CSV and the red-team
    statement with an injected instruction. Duplicates (same bytes) are listed once."""
    samples: list[SampleDoc] = []
    for path in sorted((FIXTURES / "earnings_docs").glob("*.json")):
        if path == _REDTEAM_FIXTURE:
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("member_id") == member_id:
            samples.append(_fixture_sample(path, "Your statement"))
    samples.append(_fixture_sample(_PDF_FIXTURE, "Sample PDF statement"))
    samples.append(SampleDoc(label="Sample CSV export", filename="quickdash_feb.csv", mime="text/csv",
                             data=_SAMPLE_CSV))
    samples.append(_fixture_sample(_REDTEAM_FIXTURE, "Red-team statement (contains an injected instruction)"))
    unique: list[SampleDoc] = []
    seen: set[bytes] = set()
    for s in samples:
        if s.data not in seen:
            seen.add(s.data)
            unique.append(s)
    return unique


def queue_sample(queue: list[tuple[str, bytes]], filename: str, data: bytes,
                 cap: int = 10) -> list[tuple[str, bytes]]:
    """Upload queue + one (filename, bytes) -> a new queue with it appended.

    The input list is never mutated. An exact (filename, bytes) duplicate is ignored, and once the queue holds
    `cap` items further samples are ignored.
    """
    new = list(queue)
    item = (filename, data)
    if item in new or len(new) >= cap:
        return new
    new.append(item)
    return new


def render_sample_gallery(member_id: str) -> None:
    """Streamlit: list the samples, each with a "Load into upload" button and a download button."""
    import streamlit as st

    st.subheader("Sample statements")
    for i, s in enumerate(sample_documents(member_id)):
        cols = st.columns([3, 1, 1])
        cols[0].text(f"{s.label}: {s.filename}")
        if cols[1].button("Load into upload", key=f"ui_extras_load_{member_id}_{i}"):
            st.session_state[UPLOAD_QUEUE_KEY] = queue_sample(st.session_state.get(UPLOAD_QUEUE_KEY, []),
                                                              s.filename, s.data)
        cols[2].download_button("Download", data=s.data, file_name=s.filename, mime=s.mime,
                                key=f"ui_extras_dl_{member_id}_{i}")
