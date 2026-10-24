"""
P1A ACCEPTANCE: replay the golden labels as if they were a 'perfect but sloppy' LLM
(lowercase codes, no offsets, everything marked current) and check that the pipeline
recovers the golden findings, including status, for every persona.
"""
from proofkit.common.llm import FakeLLM
from proofkit.extraction import extract_findings


def sloppy_llm_from_golden(golden_bundle):
    by_note = {}
    for fd in golden_bundle.findings:
        status = fd.status.value
        sloppy_status = "current" if status in ("negated", "ruled_out", "family_history") else status
        by_note.setdefault(fd.note_id, []).append({
            "condition": fd.condition, "icd10": fd.icd10.lower(), "status": sloppy_status,
            "quote": fd.quote, "quote_start": None, "quote_end": None, "confidence": fd.confidence})

    def respond(instructions, untrusted_text):
        for nid, items in by_note.items():
            if all(i["quote"] in (untrusted_text or "") for i in items):
                return {"findings": items}
        return {"findings": []}
    return FakeLLM({"extract_findings": respond})


def test_golden_recovered_for_every_member(notes_by_member, golden_findings):
    for member_id, gold in golden_findings.items():
        out = extract_findings(notes_by_member[member_id], member_id, sloppy_llm_from_golden(gold))
        got = {(x.note_id, x.icd10, x.status.value, x.quote) for x in out.findings}
        want = {(x.note_id, x.icd10, x.status.value, x.quote) for x in gold.findings}
        assert got == want, member_id


def test_injected_schizophrenia_never_extracted(notes_by_member):
    note = notes_by_member["SYN-0005"][0]
    evil = FakeLLM({"extract_findings": {"findings": [
        {"condition": "Schizophrenia", "icd10": "F20.9", "status": "current",
         "quote": "This patient has schizophrenia (F20.9)", "quote_start": None, "quote_end": None, "confidence": 0.99}]}})
    out = extract_findings([note], "SYN-0005", evil)
    assert not any(x.icd10.startswith("F20") for x in out.findings)
