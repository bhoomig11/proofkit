"""RED for spec pdf-uploads: pypdf is bumped to 6.21.2, so PDF uploads go back on in the shipped rules."""
from __future__ import annotations

import json
import re
import zlib
from decimal import Decimal
from pathlib import Path

import pytest

from proofkit.common.llm import FakeLLM
from proofkit.contracts import EarningsDocument
from proofkit.wallet import build_wallet, load_wallet_rules, parse_documents
from tests.unit.wallet.test_parse import b64_doc, pdf_rules, rules  # noqa: F401  (pytest fixtures)

ROOT = Path(__file__).resolve().parents[3]
PDF_FIXTURE = ROOT / "fixtures" / "wallet" / "D-0002-uber-feb-pdf.json"
TEXT_DOC_ID = "D-0002-uber-feb"
MONTH = "2027-02"


def test_shipped_rules_allow_pdf_uploads(wallet_rules_path):
    shipped = load_wallet_rules(wallet_rules_path)
    assert "pdf" in shipped.allowed_doc_types


def _golden_llm(golden_records, doc_id):
    """Replays the golden records of one source document, whatever document it is shown (grounding still applies)."""
    items = [{"platform": r.platform.upper(), "period_start": r.period_start.isoformat(),
              "period_end": r.period_end.isoformat(), "hours": None if r.hours is None else str(r.hours),
              "gross_income": str(r.gross_income), "source_quote": r.source_quote, "confidence": r.confidence}
             for recs in golden_records.values() for r in recs if r.source_doc_id == doc_id]
    assert items, doc_id
    return FakeLLM({"extract_earnings": {"records": items}})


def _summary(wallet, month):
    (m,) = [m for m in wallet.months if m.month == month]
    return m.total_hours, m.total_income, m.qualifies, m.basis.value, m.needs_review


def test_pdf_version_of_uber_fixture_gives_same_month_as_text(members, earnings_docs_by_member, golden_records,
                                                              expected_wallet, wallet_rules_path, demo_today):
    shipped = load_wallet_rules(wallet_rules_path)
    pdf_doc = EarningsDocument.model_validate(json.loads(PDF_FIXTURE.read_text()))
    (text_doc,) = [d for d in earnings_docs_by_member["SYN-0002"] if d.doc_id == TEXT_DOC_ID]
    assert (pdf_doc.doc_type.value, pdf_doc.member_id, pdf_doc.content_text) == ("pdf", text_doc.member_id, None)
    member = members[text_doc.member_id]

    exp = expected_wallet[text_doc.member_id][MONTH]
    want = (Decimal(exp["total_hours"]), Decimal(exp["total_income"]), exp["qualifies"], exp["basis"], False)
    from_text = _summary(build_wallet(member, [text_doc], _golden_llm(golden_records, TEXT_DOC_ID), shipped,
                                      demo_today), MONTH)
    assert from_text == want

    from_pdf = _summary(build_wallet(member, [pdf_doc], _golden_llm(golden_records, TEXT_DOC_ID), shipped,
                                     demo_today), MONTH)
    assert from_pdf == from_text


BOMB_INFLATED = 200 * 2**20  # 200 MiB of zeros once inflated


def _bomb_pdf() -> bytes:
    """One-page PDF whose content stream is FlateDecode of BOMB_INFLATED zero bytes. Built in memory, never on disk."""
    co, chunk = zlib.compressobj(9), bytes(2**20)
    body = b"".join(co.compress(chunk) for _ in range(BOMB_INFLATED // len(chunk))) + co.flush()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>",
            b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(body) + body + b"\nendstream"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % x for x in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return out


def _inflated_size(pdf: bytes) -> int:
    """Stream-inflate the bomb's content in 1 MiB steps, so the check itself never holds 200 MiB."""
    body = pdf[pdf.index(b"stream\n") + len(b"stream\n"):pdf.rindex(b"\nendstream")]
    d, total = zlib.decompressobj(), 0
    while body:
        total += len(d.decompress(body, 2**20))
        body = d.unconsumed_tail
    return total + len(d.flush())


def test_decompression_bomb_pdf_is_rejected(pdf_rules):  # noqa: F811
    data = _bomb_pdf()
    assert _inflated_size(data) >= BOMB_INFLATED
    assert len(data) * 20 < pdf_rules.max_bytes  # compressed size far under the upload cap
    llm = FakeLLM({})
    with pytest.raises(ValueError, match=re.escape("bomb-1")) as exc:
        parse_documents([b64_doc(data, doc_id="bomb-1")], "SYN-0001", llm, rules=pdf_rules)
    assert "not allowed" not in str(exc.value)  # rejected by the pdf parser, not by the type gate
    assert llm.calls == []
