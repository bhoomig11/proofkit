"""
Deterministic status backstop (NegEx-style), scoped to the SENTENCE that contains the quote.

It can only make a finding MORE conservative: current -> negated / ruled_out / family_history /
historical / uncertain. It never upgrades anything to current, and never overrides a non-current
status the LLM already chose.

Scope rules:
- "lead" = up to 6 words before the quote (stopping at a terminator like "but") + the quote's first 3 words.
  Cues that come BEFORE a term (denies, r/o, mother with, hx of, possible) are searched here.
- "tail" = the quote + the rest of the sentence (stopping at a terminator).
  Cues that come AFTER a term (ruled out, resolved, in remission) are searched here.
"""
from __future__ import annotations

import re

from proofkit.contracts import FindingStatus

LEAD_WORDS = 6
# sentence ends at a newline or at . ! ; followed by whitespace, but not after "vs." / "Dr."
_SENTENCE_END = re.compile(r"\n|(?<!\bvs)(?<!\bDr)[.!;](?=\s)")
_TERMINATOR = re.compile(r"\b(but|however|although|though|except|aside from|apart from)\b", re.I)

_RELATIVE = r"(mother|mom|father|dad|sister|brother|sibling|son|daughter|aunt|uncle|grandmother|grandfather|cousin|parent)s?"
_UNCERTAIN_FIRST = re.compile(r"\b(cannot|can't|can not) rule out\b", re.I)
_LEAD_CUES = [
    (FindingStatus.NEGATED, re.compile(r"\b(denies|denied|deny|no|not|negative for|without|free of|absence of)\b", re.I)),
    (FindingStatus.RULED_OUT, re.compile(r"(?<!\w)(r/o|rule out|ruled out|rules out)\b", re.I)),
    (FindingStatus.FAMILY_HISTORY, re.compile(
        rf"\b(family history|family hx|fhx|fh)\b|\b{_RELATIVE}('s|\s+(with|has|had|history|hx|diagnosed))\b", re.I)),
    (FindingStatus.HISTORICAL, re.compile(
        r"(?<!\w)(hx of|history of|h/o|s/p|status post|past history of|remote history of)(?!\w)", re.I)),
    (FindingStatus.UNCERTAIN, re.compile(
        r"\b(possible|possibly|probable|probably|likely|suspected|suspect|suspicious for|concern for|"
        r"concerning for|questionable|presumed|may have)\b", re.I)),
]
_TAIL_CUES = [
    (FindingStatus.RULED_OUT, re.compile(r"\b(ruled out|excluded)\b", re.I)),
    (FindingStatus.HISTORICAL, re.compile(r"\b(resolved|in remission|no longer)\b", re.I)),
]
_PRIORITY = [FindingStatus.NEGATED, FindingStatus.RULED_OUT, FindingStatus.FAMILY_HISTORY,
             FindingStatus.HISTORICAL, FindingStatus.UNCERTAIN]


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    s0 = 0
    for m in _SENTENCE_END.finditer(text, 0, start):
        s0 = m.end()
    m = _SENTENCE_END.search(text, end)
    return s0, (m.start() if m else len(text))


def detect_status(text: str, start: int, end: int) -> FindingStatus | None:
    """Return the status implied by cues around text[start:end] in its sentence, or None if no cue."""
    s0, s1 = _sentence_bounds(text, start, end)
    before = text[s0:start]
    cut = [m.end() for m in _TERMINATOR.finditer(before)]
    if cut:
        before = before[cut[-1]:]
    before_words = before.split()
    lead_prefix = " ".join(before_words[-LEAD_WORDS:])
    quote = text[start:end]
    lead = f"{lead_prefix} {' '.join(quote.split()[:3])}".strip()

    after = text[end:s1]
    m = _TERMINATOR.search(after)
    tail = quote + (after[: m.start()] if m else after)

    if _UNCERTAIN_FIRST.search(lead):
        return FindingStatus.UNCERTAIN
    hits = {status for status, rx in _LEAD_CUES if rx.search(lead)}
    hits |= {status for status, rx in _TAIL_CUES if rx.search(tail)}
    if before.rstrip().endswith("?") or text[end:end + 1] == "?" or quote.endswith("?"):
        hits.add(FindingStatus.UNCERTAIN)
    return next((s for s in _PRIORITY if s in hits), None)


def apply_backstop(llm_status: FindingStatus, text: str, start: int, end: int) -> FindingStatus:
    """Only ever downgrade CURRENT. Any other LLM status is kept as is."""
    if llm_status != FindingStatus.CURRENT:
        return llm_status
    return detect_status(text, start, end) or FindingStatus.CURRENT
