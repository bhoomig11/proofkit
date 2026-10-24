"""
P1A owns this file. Build it TEST-FIRST (tests/unit/extraction/test_extraction_spec.py).

Suggested internal layout (create as you go, each with its own tests):
  prompts.py    instruction text for task="extract_findings" (no untrusted text in here)
  normalize.py  ICD-10 normalisation (case, dot placement, validation)
  status.py     deterministic NegEx-style backstop: negated / ruled_out / family_history / historical / uncertain
  ground.py     uses proofkit.common.grounding + proofkit.common.injection to keep only safe, grounded findings
"""
from __future__ import annotations

from proofkit.common.llm import LLMClient
from proofkit.contracts import ClinicalNote, FindingsBundle

EXTRACTOR_VERSION = "p1a-0.0.0"

# The FakeLLM / real LLM is called with task="extract_findings" ONCE PER NOTE and must return:
# {"findings": [{"condition": str, "icd10": str, "status": str, "quote": str,
#                "quote_start": int|null, "quote_end": int|null, "confidence": float}]}
LLM_TASK = "extract_findings"


def extract_findings(notes: list[ClinicalNote], member_id: str, llm: LLMClient) -> FindingsBundle:
    """ClinicalNote[] -> FindingsBundle. Every returned Finding is grounded, safe, and has a valid ICD-10 code."""
    raise NotImplementedError("P1A: implement test-first")
