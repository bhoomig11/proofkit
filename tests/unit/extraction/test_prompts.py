"""P1A own tests: the extraction prompt (prompts.py)."""
from datetime import date

from proofkit.common.llm import FakeLLM
from proofkit.contracts import ClinicalNote, FindingStatus
from proofkit.extraction import extract_findings
from proofkit.extraction.prompts import EXTRACTION_INSTRUCTIONS


def test_prompt_names_every_status():
    for status in FindingStatus:
        assert f'"{status.value}"' in EXTRACTION_INSTRUCTIONS


def test_prompt_has_few_shot_examples_for_negation_ruleout_and_family_history():
    for phrase in ("Denies chest pain", "R/o CHF", "Mother with breast cancer"):
        assert phrase in EXTRACTION_INSTRUCTIONS


def test_prompt_states_coding_convention_and_empty_result():
    assert "C50.919" in EXTRACTION_INSTRUCTIONS  # condition's own code for family history
    assert "Z80" in EXTRACTION_INSTRUCTIONS        # ...explicitly not the Z history codes
    assert '{"findings": []}' in EXTRACTION_INSTRUCTIONS


def test_pipeline_sends_the_prompt_and_never_the_note_in_instructions():
    text = "Assessment: right ankle sprain, grade 1. Unique-marker-7f3a."
    note = ClinicalNote(note_id="N-P-1", member_id="SYN-0001", note_date=date(2026, 1, 1), text=text)
    llm = FakeLLM({"extract_findings": {"findings": []}})
    extract_findings([note], "SYN-0001", llm)
    call = llm.calls[0]
    assert call["instructions"] == EXTRACTION_INSTRUCTIONS
    assert "Unique-marker-7f3a" not in call["instructions"]
    assert "Unique-marker-7f3a" in call["user"]


def test_few_shot_offsets_are_correct():
    """Every example quote must sit exactly at its stated offsets, or the prompt teaches wrong offsets."""
    import json
    import re

    blocks = re.findall(r'Note: "(.*?)"\n(\{"findings": \[.*?\]\})', EXTRACTION_INSTRUCTIONS, re.S)
    assert len(blocks) == 3
    for note_text, payload in blocks:
        for f in json.loads(payload)["findings"]:
            assert note_text[f["quote_start"]:f["quote_end"]] == f["quote"], f["quote"]
