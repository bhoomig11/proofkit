"""ICD-10 normalisation: case, whitespace, and dot placement, validated against the contract pattern."""
from __future__ import annotations

import re

from proofkit.contracts import ICD10_PATTERN

_ICD10 = re.compile(ICD10_PATTERN)


def normalize_icd10(raw: object) -> str | None:
    """Return the code as uppercase with a dot after 3 characters (M329 -> M32.9), or None if invalid."""
    if not isinstance(raw, str):
        return None
    code = re.sub(r"\s+", "", raw).upper()
    if "." not in code and len(code) > 3:
        code = f"{code[:3]}.{code[3:]}"
    return code if _ICD10.match(code) else None
