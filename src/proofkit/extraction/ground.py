"""Grounding: re-locate every LLM quote in the real note text. The LLM's offsets are only a hint."""
from __future__ import annotations

from proofkit.common.grounding import Span, locate_quote


def ground_quote(text: str, quote: object, hint_start: object) -> Span | None:
    """Return the span of `quote` in `text` (the ORIGINAL slice), or None if it isn't really there."""
    if not isinstance(quote, str):
        return None
    hint = hint_start if isinstance(hint_start, int) and not isinstance(hint_start, bool) else None
    return locate_quote(text, quote, hint)
