"""P1A own tests: deterministic status backstop (status.py), sentence-scoped NegEx-style cues."""
import pytest

from proofkit.contracts import FindingStatus as S
from proofkit.extraction.status import apply_backstop, detect_status

N, R, F, H, U, C = S.NEGATED, S.RULED_OUT, S.FAMILY_HISTORY, S.HISTORICAL, S.UNCERTAIN, S.CURRENT

CASES = [
    # negated
    ("Patient denies chest pain.", "chest pain", N),
    ("Denies chest pain.", "Denies chest pain", N),
    ("No shortness of breath.", "shortness of breath", N),
    ("Negative for pneumonia on CXR.", "pneumonia", N),
    ("No evidence of malignancy.", "malignancy", N),
    ("No history of seizures.", "seizures", N),  # "no history of" is NEGATED, not historical
    ("Patient denies depression or anxiety.", "anxiety", N),  # cue carries across "or"
    ("Afebrile, without rash.", "rash", N),
    # ruled out
    ("R/o CHF; BNP pending.", "CHF", R),
    ("R/o CHF; BNP pending.", "R/o CHF", R),
    ("Echo normal. Heart failure ruled out.", "Heart failure", R),  # cue after the term
    ("Rule out pulmonary embolism.", "pulmonary embolism", R),
    ("r/o pneumonia vs. bronchitis.", "bronchitis", R),  # "vs." must not end the sentence
    # family history
    ("Mother with rheumatoid arthritis.", "rheumatoid arthritis", F),
    ("Family hx: mother with rheumatoid arthritis.", "mother with rheumatoid arthritis", F),
    ("FHx of colon cancer in father.", "colon cancer", F),
    ("Her brother has schizophrenia.", "schizophrenia", F),
    # historical
    ("PMH: hx of iron deficiency anemia, resolved 2024.", "iron deficiency anemia", H),
    ("History of PTSD, symptoms resolved with therapy.", "PTSD", H),
    ("S/p appendectomy for appendicitis in 2019.", "appendicitis", H),
    ("Depression in remission since 2021.", "Depression", H),  # cue after the term
    ("h/o DVT.", "DVT", H),
    # uncertain
    ("Possible mild intermittent asthma.", "mild intermittent asthma", U),
    ("Concern for bipolar disorder; referred to psychiatry.", "bipolar disorder", U),
    ("Suspected gout of the left toe.", "gout", U),
    ("? early cellulitis of left leg.", "early cellulitis", U),
    ("Cannot rule out early appendicitis.", "early appendicitis", U),
    # stays current
    ("Systemic lupus erythematosus, active flare.", "Systemic lupus erythematosus", C),
    ("PMH: hx of iron deficiency anemia, resolved 2024. SLE followed by rheum.", "SLE followed by rheum", C),  # N-0001-b
    ("Major depressive disorder, recurrent, severe without psychotic features.",
     "Major depressive disorder, recurrent, severe without psychotic features", C),  # "without" follows the term
    ("Assessment: dyspnea on exertion, likely deconditioning.", "dyspnea on exertion", C),  # "likely" is about the other term
    ("No fever, but reports productive cough from bronchitis.", "bronchitis", C),  # "but" ends the negation
    ("Patient denies depression. Essential hypertension, controlled.", "Essential hypertension", C),
    ("Anemia, stable on recheck.", "Anemia", C),
    ("Epilepsy, seizure-free on current medication.", "Epilepsy", C),
    ("No prior cardiac history.\nHypertension well controlled.", "Hypertension", C),  # newline ends the sentence
]


def _span(text, quote):
    start = text.index(quote)
    return start, start + len(quote)


@pytest.mark.parametrize("text,quote,expected", CASES, ids=[f"{c[2].value}:{c[1]}" for c in CASES])
def test_backstop_corrects_llm_saying_current(text, quote, expected):
    start, end = _span(text, quote)
    assert apply_backstop(C, text, start, end) == expected


def test_table_has_at_least_25_cases():
    assert len(CASES) >= 25


@pytest.mark.parametrize("llm_status", [N, R, F, H, U])
def test_never_upgrades_to_current(llm_status):
    text = "Systemic lupus erythematosus, active flare."
    start, end = _span(text, "Systemic lupus erythematosus")
    assert detect_status(text, start, end) is None
    assert apply_backstop(llm_status, text, start, end) == llm_status


def test_never_overrides_a_non_current_llm_status():
    text = "Patient denies chest pain."
    start, end = _span(text, "chest pain")
    assert apply_backstop(U, text, start, end) == U
