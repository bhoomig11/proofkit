"""Pure escaping and exact-offset highlighting helpers."""
from __future__ import annotations

import html


def escape_plain(value: str) -> str:
    """Escape dynamic text for safe insertion into HTML."""
    return html.escape(value, quote=True)


def highlight_quote(text: str, start: int, end: int) -> str:
    """Escape a source string and wrap exactly its selected slice in one mark element."""
    if start < 0 or end <= start or end > len(text):
        raise ValueError("quote offsets must select a non-empty slice inside the text")
    before = html.escape(text[:start], quote=True)
    quote = html.escape(text[start:end], quote=True)
    after = html.escape(text[end:], quote=True)
    return f"{before}<mark>{quote}</mark>{after}"
