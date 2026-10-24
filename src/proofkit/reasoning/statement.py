"""
P1B owns this. Draft the clinician attestation for EXEMPT / NEEDS_CLINICIAN_REVIEW decisions.

The structure comes from a fixed template; the LLM (task="draft_statement") writes ONLY the short
clinical-summary paragraph and must return {"summary": str}. Validate the summary: it must not mention
ICD-10 codes or conditions that aren't in the decision's evidence. If it fails, fall back to a template-only
summary. The statement must say a licensed clinician must review and sign it.
"""
from __future__ import annotations

from proofkit.common.llm import LLMClient
from proofkit.contracts import ExemptionDecision, FindingsBundle, Member

LLM_TASK = "draft_statement"


def draft_statement(decision: ExemptionDecision, bundle: FindingsBundle, member: Member, llm: LLMClient) -> str:
    raise NotImplementedError("P1B: implement test-first")
