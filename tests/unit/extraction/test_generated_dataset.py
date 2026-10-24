"""
P1A own tests: the generated synthetic dataset (fixtures/notes/generated, fixtures/findings/generated).

These members (SYN-0006 and up) live in subfolders so the frozen contract suite, which expects exactly the
5 seed members at the top level, is unaffected. The checks mirror the seed acceptance test.
"""
import json
from pathlib import Path

import pytest
from tests.acceptance.test_extraction_golden import sloppy_llm_from_golden

from proofkit.contracts import ClinicalNote, FindingsBundle
from proofkit.extraction import extract_findings

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
SEEDS = {m["member_id"] for m in json.loads((FIXTURES / "members" / "members.json").read_text())["members"]}


def _notes():
    out = {}
    for p in sorted((FIXTURES / "notes" / "generated").glob("*.json")):
        n = ClinicalNote.model_validate_json(p.read_text())
        out.setdefault(n.member_id, []).append(n)
    return out


def _golden():
    return {p.name.split(".")[0]: FindingsBundle.model_validate_json(p.read_text())
            for p in sorted((FIXTURES / "findings" / "generated").glob("*.golden.json"))}


NOTES, GOLDEN = _notes(), _golden()


def test_generated_dataset_is_present_and_separate_from_seeds():
    assert len(GOLDEN) >= 50
    assert set(GOLDEN) == set(NOTES)
    assert not set(GOLDEN) & SEEDS


@pytest.mark.parametrize("member_id", sorted(GOLDEN))
def test_generated_golden_is_grounded_and_in_quote_order(member_id):
    texts = {n.note_id: n.text for n in NOTES[member_id]}
    by_note = {}
    for f in GOLDEN[member_id].findings:
        assert texts[f.note_id][f.quote_start:f.quote_end] == f.quote, f.finding_id
        by_note.setdefault(f.note_id, []).append(f)
    for note_id, items in by_note.items():
        ordered = sorted(items, key=lambda f: (f.quote_start, f.icd10))
        assert [f.finding_id for f in ordered] == [f"F-{note_id}-{i}" for i in range(len(ordered))]


@pytest.mark.parametrize("member_id", sorted(GOLDEN))
def test_extraction_recovers_generated_golden(member_id):
    gold = GOLDEN[member_id]
    out = extract_findings(NOTES[member_id], member_id, sloppy_llm_from_golden(gold))
    key = lambda f: (f.finding_id, f.note_id, f.icd10, f.status.value, f.quote)  # noqa: E731
    assert {key(f) for f in out.findings} == {key(f) for f in gold.findings}
