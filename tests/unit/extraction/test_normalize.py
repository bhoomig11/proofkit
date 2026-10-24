"""P1A own tests: ICD-10 normalisation table (normalize.py)."""
import pytest

from proofkit.extraction.normalize import normalize_icd10


@pytest.mark.parametrize("raw,expected", [
    ("M32.9", "M32.9"),
    ("m32.9", "M32.9"),
    ("M329", "M32.9"),
    (" M32.14 ", "M32.14"),
    ("m3214", "M32.14"),
    ("S93.401A", "S93.401A"),
    ("s93401a", "S93.401A"),
    ("I10", "I10"),
    ("i10", "I10"),
    ("F32.A", "F32.A"),
    ("F32A", "F32.A"),
    ("R07 .9", "R07.9"),
])
def test_valid_codes_are_normalised(raw, expected):
    assert normalize_icd10(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", "LUPUS", "M3", "32.9", "MM2.9", "M32.", "M32.12345", "M32..9", "M3-2.9", None, 329,
])
def test_invalid_codes_return_none(raw):
    assert normalize_icd10(raw) is None
