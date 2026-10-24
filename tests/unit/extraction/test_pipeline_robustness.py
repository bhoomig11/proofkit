"""P1A own tests: pipeline edge cases (bad LLM output, retries, long notes, duplicates, ordering)."""
from datetime import date

from proofkit.common.llm import FakeLLM, LLMError
from proofkit.contracts import ClinicalNote, FindingStatus
from proofkit.extraction import extract_findings


def note(text, note_id="N-R-1"):
    return ClinicalNote(note_id=note_id, member_id="SYN-0001", note_date=date(2026, 11, 10), text=text)


def item(quote, icd="I10", status="current", start=None, conf=0.9):
    return {"condition": "c", "icd10": icd, "status": status, "quote": quote,
            "quote_start": start, "quote_end": None, "confidence": conf}


def test_duplicate_quote_uses_hint_to_pick_the_right_occurrence():
    text = "Essential hypertension, controlled. Plan: recheck. Essential hypertension, review in 3 months."
    second = text.index("Essential hypertension", 10)
    out = extract_findings([note(text)], "SYN-0001",
                           FakeLLM({"extract_findings": {"findings": [item("Essential hypertension", start=second - 2)]}}))
    assert out.findings[0].quote_start == second


def test_empty_llm_response_gives_no_findings_but_note_is_processed():
    out = extract_findings([note("Well visit, no concerns.")], "SYN-0001", FakeLLM({"extract_findings": {"findings": []}}))
    assert out.findings == [] and out.notes_processed == ["N-R-1"] and out.dropped_ungrounded == 0


def test_wrong_type_response_is_a_failure_not_a_crash():
    llm = FakeLLM({"extract_findings": "here are the findings: hypertension"})
    out = extract_findings([note("Essential hypertension.")], "SYN-0001", llm)
    assert len(llm.calls) == 2  # retried once
    assert out.notes_processed == [] and out.findings == []


def test_findings_not_a_list_is_a_failure():
    llm = FakeLLM({"extract_findings": {"findings": "hypertension"}})
    out = extract_findings([note("Essential hypertension.")], "SYN-0001", llm)
    assert len(llm.calls) == 2 and out.notes_processed == []


def test_retry_that_succeeds_processes_the_note():
    calls = {"n": 0}

    def flaky_once(instructions, untrusted):
        calls["n"] += 1
        if calls["n"] == 1:
            raise LLMError("timeout")
        return {"findings": [item("Essential hypertension")]}

    out = extract_findings([note("Essential hypertension.")], "SYN-0001", FakeLLM({"extract_findings": flaky_once}))
    assert calls["n"] == 2 and out.notes_processed == ["N-R-1"] and len(out.findings) == 1


def test_failed_note_does_not_stop_the_next_note():
    def by_note(instructions, untrusted):
        if "BROKEN" in untrusted:
            raise LLMError("bad json")
        return {"findings": [item("Essential hypertension")]}

    notes = [note("BROKEN note.", "N-R-1"), note("Essential hypertension.", "N-R-2")]
    out = extract_findings(notes, "SYN-0001", FakeLLM({"extract_findings": by_note}))
    assert out.notes_processed == ["N-R-2"] and [f.note_id for f in out.findings] == ["N-R-2"]


def test_40k_char_note_makes_exactly_one_call():
    text = ("Patient doing well. " * 2000)[:39_900] + " Essential hypertension."
    assert len(text) >= 39_900
    llm = FakeLLM({"extract_findings": {"findings": [item("Essential hypertension")]}})
    out = extract_findings([note(text)], "SYN-0001", llm)
    assert len(llm.calls) == 1
    assert out.findings[0].quote == "Essential hypertension"


def test_identical_findings_are_deduplicated():
    llm = FakeLLM({"extract_findings": {"findings": [item("Essential hypertension"), item("essential hypertension".capitalize())]}})
    out = extract_findings([note("Essential hypertension.")], "SYN-0001", llm)
    assert len(out.findings) == 1


def test_invalid_status_or_non_dict_item_is_dropped_and_counted():
    llm = FakeLLM({"extract_findings": {"findings": [item("Essential hypertension", status="active"), "junk", 42]}})
    out = extract_findings([note("Essential hypertension.")], "SYN-0001", llm)
    assert out.findings == [] and out.dropped_ungrounded == 3


def test_bad_confidence_is_dropped_and_counted():
    llm = FakeLLM({"extract_findings": {"findings": [item("Essential hypertension", conf=1.7)]}})
    out = extract_findings([note("Essential hypertension.")], "SYN-0001", llm)
    assert out.findings == [] and out.dropped_ungrounded == 1


def test_ids_follow_quote_position_not_llm_order():
    text = "Essential hypertension. Asthma, uncomplicated."
    llm = FakeLLM({"extract_findings": {"findings": [item("Asthma, uncomplicated", icd="J45.909"),
                                                     item("Essential hypertension")]}})
    out = extract_findings([note(text)], "SYN-0001", llm)
    assert [(f.finding_id, f.icd10) for f in out.findings] == [("F-N-R-1-0", "I10"), ("F-N-R-1-1", "J45.909")]


def test_backstop_applies_inside_the_pipeline():
    text = "Patient denies depression."
    llm = FakeLLM({"extract_findings": {"findings": [item("denies depression", icd="F32.A")]}})
    out = extract_findings([note(text)], "SYN-0001", llm)
    assert out.findings[0].status == FindingStatus.NEGATED


def test_ids_stay_contiguous_when_an_item_fails_validation():
    text = "Essential hypertension. Asthma, uncomplicated. Anemia."
    llm = FakeLLM({"extract_findings": {"findings": [item("Essential hypertension"),
                                                     item("Asthma, uncomplicated", icd="J45.909", conf=1.7),
                                                     item("Anemia", icd="D64.9")]}})
    out = extract_findings([note(text)], "SYN-0001", llm)
    assert [f.finding_id for f in out.findings] == ["F-N-R-1-0", "F-N-R-1-1"]
    assert out.dropped_ungrounded == 1
