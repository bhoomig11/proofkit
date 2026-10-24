"""
Heuristic detector for prompt-injection text inside untrusted documents.

This is defense in depth, not a guarantee. The real protections are:
(1) delimiters plus the guard in llm.py, (2) grounding, (3) deterministic decision code.
Modules must DROP any extracted item whose quote overlaps an injection span.
"""
from __future__ import annotations

import re

_INJECTION_PATTERNS = [
    r"ignore (all )?(prior|previous|above) (instructions|prompts)",
    r"disregard (all )?(prior|previous|above)",
    r"\b(system|developer) (note|message|prompt)\b.{0,20}\b(ai|assistant|model|llm)\b",
    r"^\s*system\s*:",
    r"\bassistant\s*,",
    r"\byou (must|should) (now )?(mark|report|classify|output|say)\b",
    r"\bmust be marked\b",
    r"\breport this (worker|patient|member) as\b",
    r"\bnew instructions\b",
    r"\bact as\b.{0,30}\b(admin|system|developer)\b",
]
_RX = [re.compile(p, re.I | re.M) for p in _INJECTION_PATTERNS]
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")


def looks_like_injection(text: str) -> bool:
    return any(rx.search(text) for rx in _RX)


def injection_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of SENTENCES/LINES that look like injected instructions.

    The sentence following an instruction sentence on the same line is included too, because injected
    payloads often continue across sentences ("Ignore ... . This patient has X and must be marked ...").
    """
    spans: list[tuple[int, int]] = []
    for line_m in re.finditer(r"[^\n]+", text):
        line, base = line_m.group(0), line_m.start()
        if looks_like_injection(line):
            spans.append((base, base + len(line)))  # whole line is tainted
    return spans


def overlaps_injection(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < e and s < end for s, e in spans)
