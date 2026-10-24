"""
P2 owns this. Untrusted documents -> EarningsRecord[].

- CSV: parse deterministically with the csv module (no LLM).
- TEXT: LLM task="extract_earnings", returning {"records": [{"platform","period_start","period_end","hours","gross_income","source_quote","confidence"}]}
- PDF: extract text (pypdf, page cap from rules), then the same as TEXT.
- IMAGE: stretch goal. For now return no records for it; the evaluate step flags the month for review.
Every LLM record must pass: the source_quote is found in the document, it doesn't overlap injection_spans,
the numbers in the record appear in the source_quote, and it validates against the contract.
"""
from __future__ import annotations

from proofkit.common.llm import LLMClient
from proofkit.contracts import EarningsDocument, EarningsRecord

LLM_TASK = "extract_earnings"


def parse_documents(docs: list[EarningsDocument], member_id: str, llm: LLMClient) -> list[EarningsRecord]:
    raise NotImplementedError("P2: implement test-first")
