"""P1B owns this. ICD-10 prefix matching on code boundaries (pure)."""
from __future__ import annotations


def icd_matches(code: str, prefix: str) -> bool:
    """True if ICD-10 `code` falls under rule `prefix`.

    A category prefix ("F31") matches the category itself and its subcodes ("F31", "F31.9") only.
    A subcategory prefix ("F32.2") matches codes that extend it ("F32.2", "F32.29"), never siblings ("F32.9").
    """
    code, prefix = code.upper(), prefix.upper()
    if "." not in prefix:
        return code == prefix or code.startswith(prefix + ".")
    return code.startswith(prefix)
