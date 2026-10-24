"""
Grounding: prove that a quote really appears in its source text.

LLMs often get character offsets wrong, so `locate_quote` searches for the quote and
returns the real offsets. A finding whose quote can't be located must be DROPPED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


def verify_span(source: str, quote: str, start: int, end: int) -> bool:
    """True iff source[start:end] == quote exactly."""
    return 0 <= start < end <= len(source) and source[start:end] == quote


def locate_quote(source: str, quote: str, hint_start: int | None = None) -> Span | None:
    """
    Find `quote` in `source`. Strategy:
      1. exact match (closest to hint_start if there are several)
      2. whitespace-insensitive match (LLMs collapse newlines/spaces). Returns the ORIGINAL source slice
    Returns None if not found. Never returns a span whose text isn't literally in source.
    """
    if not quote or not quote.strip():
        return None
    exact = [m.start() for m in re.finditer(re.escape(quote), source)]
    if exact:
        s = min(exact, key=lambda i: abs(i - hint_start)) if hint_start is not None else exact[0]
        return Span(s, s + len(quote), source[s : s + len(quote)])
    tokens = quote.split()
    pattern = r"\s+".join(re.escape(t) for t in tokens)
    matches = list(re.finditer(pattern, source))
    if not matches:
        return None
    m = min(matches, key=lambda x: abs(x.start() - hint_start)) if hint_start is not None else matches[0]
    return Span(m.start(), m.end(), source[m.start() : m.end()])
