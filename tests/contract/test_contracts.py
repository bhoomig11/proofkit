"""FROZEN contract tests. They must be green on every branch at every commit."""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from proofkit.contracts import (
    DecisionOutcome, EarningsDocument, EarningsRecord, ExemptionDecision,
    ExemptionType, Finding, FindingsBundle, FindingStatus, Member, MonthlyCompliance, ComplianceBasis,
)

ROOT = Path(__file__).resolve().parents[2]


def test_contract_lock_matches():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "contract_lock.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_all_fixtures_validate(members, notes_by_member, golden_findings, earnings_docs_by_member, golden_records):
    assert len(members) == 5
    assert sum(len(v) for v in notes_by_member.values()) >= 8
    assert set(golden_findings) == set(members)
    assert sum(len(v) for v in earnings_docs_by_member.values()) >= 8
    assert golden_records


def test_golden_findings_are_grounded(notes_by_member, golden_findings):
    notes = {n.note_id: n for ns in notes_by_member.values() for n in ns}
    for bundle in golden_findings.values():
        for f in bundle.findings:
            assert notes[f.note_id].text[f.quote_start:f.quote_end] == f.quote, f.finding_id


def test_golden_records_are_grounded(earnings_docs_by_member, golden_records):
    docs = {d.doc_id: d for ds in earnings_docs_by_member.values() for d in ds}
    for recs in golden_records.values():
        for r in recs:
            assert r.source_quote in docs[r.source_doc_id].content_text, r.record_id


def test_only_synthetic_member_ids():
    with pytest.raises(ValidationError):
        Member(member_id="12345", display_name="x", renewal_date=date(2027, 1, 1))


def test_finding_offsets_must_match_quote_length():
    with pytest.raises(ValidationError):
        Finding(finding_id="f1", note_id="n", note_date=date(2026, 1, 1), condition="c", icd10="M32.9",
                status=FindingStatus.CURRENT, quote="lupus", quote_start=0, quote_end=99, confidence=0.9)


@pytest.mark.parametrize("bad", ["m32.9", "M329X.12345", "32.9", "1234", ""])
def test_icd10_format_rejected(bad):
    with pytest.raises(ValidationError):
        Finding(finding_id="f1", note_id="n", note_date=date(2026, 1, 1), condition="c", icd10=bad,
                status=FindingStatus.CURRENT, quote="x", quote_start=0, quote_end=1, confidence=0.9)


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        Member(member_id="SYN-0001", display_name="x", renewal_date=date(2027, 1, 1), ssn="000-00-0000")


def test_exempt_requires_evidence():
    with pytest.raises(ValidationError):
        ExemptionDecision(member_id="SYN-0001", outcome=DecisionOutcome.EXEMPT, exemption_type=ExemptionType.MEDICALLY_FRAIL,
                          confidence=0.9, matched_rules=[], evidence_finding_ids=[], lookback_months=12,
                          as_of=date(2027, 3, 1), rules_version="x")


def test_review_requires_reasons():
    with pytest.raises(ValidationError):
        ExemptionDecision(member_id="SYN-0001", outcome=DecisionOutcome.NEEDS_CLINICIAN_REVIEW, exemption_type=ExemptionType.NONE,
                          confidence=0.5, matched_rules=[], evidence_finding_ids=[], lookback_months=12,
                          as_of=date(2027, 3, 1), rules_version="x")


def test_earnings_record_max_31_days():
    with pytest.raises(ValidationError):
        EarningsRecord(record_id="r", member_id="SYN-0001", source_doc_id="d", platform="uber",
                       period_start=date(2027, 1, 1), period_end=date(2027, 3, 1), gross_income=Decimal("1"),
                       source_quote="x", confidence=0.9)


def test_money_is_decimal_not_float():
    r = EarningsRecord(record_id="r", member_id="SYN-0001", source_doc_id="d", platform="uber",
                       period_start=date(2027, 1, 1), period_end=date(2027, 1, 31), gross_income="598.20",
                       source_quote="x", confidence=0.9)
    assert isinstance(r.gross_income, Decimal)


def test_monthly_qualifies_iff_basis():
    with pytest.raises(ValidationError):
        MonthlyCompliance(month="2027-02", total_hours=Decimal("10"), hours_known_for_all_records=True,
                          total_income=Decimal("10"), qualifies=True, basis=ComplianceBasis.NONE,
                          shortfall_hours=Decimal("70"), shortfall_income=Decimal("570"), record_ids=[])


def test_document_exactly_one_content():
    with pytest.raises(ValidationError):
        EarningsDocument(doc_id="d", member_id="SYN-0001", filename="a.txt", doc_type="text")


def test_models_round_trip_json(golden_findings):
    for b in golden_findings.values():
        assert FindingsBundle.model_validate_json(b.model_dump_json()) == b
