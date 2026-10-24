"""
P1A golden-ID checks (run by make test-p1a): finding IDs are F-{note_id}-{i} in quote order, in the golden files AND in real output.
P1B's expected decisions reference these IDs, so a numbering mismatch breaks integration even when the
findings themselves are right.
"""
from tests.acceptance.test_extraction_golden import sloppy_llm_from_golden

from proofkit.extraction import extract_findings


def test_golden_ids_follow_quote_order(golden_findings):
    for member_id, gold in golden_findings.items():
        by_note = {}
        for f in gold.findings:
            by_note.setdefault(f.note_id, []).append(f)
        for note_id, items in by_note.items():
            ordered = sorted(items, key=lambda f: (f.quote_start, f.icd10))
            assert [f.finding_id for f in ordered] == [f"F-{note_id}-{i}" for i in range(len(ordered))], note_id


def test_extracted_ids_match_golden_ids(notes_by_member, golden_findings):
    for member_id, gold in golden_findings.items():
        out = extract_findings(notes_by_member[member_id], member_id, sloppy_llm_from_golden(gold))
        got = {(f.note_id, f.icd10, f.quote): f.finding_id for f in out.findings}
        want = {(f.note_id, f.icd10, f.quote): f.finding_id for f in gold.findings}
        assert got == want, member_id
