"""Build fixtures/wallet/D-0002-ridenow-feb-pdf.json: the RideNow text fixture rendered as a one-page PDF.

Run once from the repo root:  .venv/Scripts/python tests/unit/wallet/make_pdf_fixture.py
Not a test module (pytest only collects test_*.py). Deterministic: rerunning gives the same bytes.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from proofkit.contracts import EarningsDocument  # noqa: E402
from tests.unit.wallet.test_parse import pdf_bytes  # noqa: E402

SOURCE = ROOT / "fixtures" / "earnings_docs" / "D-0002-ridenow-feb.json"
TARGET = ROOT / "fixtures" / "wallet" / "D-0002-ridenow-feb-pdf.json"


def main() -> None:
    src = EarningsDocument.model_validate(json.loads(SOURCE.read_text()))
    text = (src.content_text or "").rstrip("\n")
    # pdf_bytes writes each line as a literal string; these characters would need PDF escaping.
    if any(c in text for c in "()\\"):
        raise SystemExit("source text needs PDF string escaping; pdf_bytes does not do that")
    doc = EarningsDocument(doc_id="D-0002-ridenow-feb-pdf", member_id=src.member_id, filename="ridenow-feb.pdf",
                           doc_type="pdf", content_b64=base64.b64encode(pdf_bytes(text)).decode())
    TARGET.write_text(json.dumps(doc.model_dump(mode="json", exclude_none=True), indent=2) + "\n")
    print(f"wrote {TARGET.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
