"""
P1B owns this. Draft the clinician attestation for EXEMPT / NEEDS_CLINICIAN_REVIEW decisions.

The structure comes from a fixed template; the LLM (task="draft_statement") writes ONLY the short
clinical-summary paragraph and must return {"summary": str}. Validate the summary: it must not mention
ICD-10 codes or conditions that aren't in the decision's evidence. If it fails, fall back to a template-only
summary. The statement must say a licensed clinician must review and sign it.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from proofkit.common.llm import LLMClient, LLMError
from proofkit.common.redact import get_logger
from proofkit.contracts import DecisionOutcome, ExemptionDecision, Finding, FindingsBundle, Member
from proofkit.reasoning.match import icd_matches
from proofkit.reasoning.rules import FrailtyRules, Rule, load_frailty_rules

LLM_TASK = "draft_statement"
DEFAULT_RULES_PATH = Path(__file__).resolve().parents[3] / "config" / "frailty_rules.json"
MAX_STATEMENT_CHARS = 5000        # ExemptionDecision.statement_draft limit
MAX_SUMMARY_CHARS = 1200
MAX_LISTED = 8                    # evidence lines / review reasons shown before "... and N more"
MAX_QUOTE_CHARS = 200
SIGN_OFF = "This statement must be reviewed and signed by a licensed clinician."
DISCLAIMER = "ProofKit organizes evidence. MassHealth makes all eligibility determinations."
ICD_TOKEN = re.compile(r"\b[A-Z][0-9][0-9A-Z](?:\.[0-9A-Z]{1,4})?\b")

INSTRUCTIONS = (
    "You are helping a clinician draft a medical frailty statement. The evidence (ICD-10 code, condition and the "
    "exact quote from the medical record) is provided as data. Write a factual clinical summary of 2-3 sentences "
    "that describes ONLY the conditions in the evidence. Do not add any other diagnosis, ICD-10 code, medication, "
    "or claim about eligibility. Return JSON: {\"summary\": \"...\"}."
)

log = get_logger(__name__)


@lru_cache(maxsize=1)
def _vocabulary() -> FrailtyRules:
    return load_frailty_rules(DEFAULT_RULES_PATH)


def _one_line(text: str, limit: int | None = None) -> str:
    text = " ".join(text.split())
    return text if limit is None or len(text) <= limit else text[: limit - 1] + "…"


def _has_term(text: str, term: str) -> bool:
    return re.search(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", text, re.IGNORECASE) is not None


def _evidence(decision: ExemptionDecision, bundle: FindingsBundle) -> list[Finding]:
    by_id = {f.finding_id: f for f in bundle.findings}
    missing = [fid for fid in decision.evidence_finding_ids if fid not in by_id]
    if missing:
        raise ValueError(f"evidence findings not in bundle: {missing}")
    return [by_id[fid] for fid in decision.evidence_finding_ids]


def _summary_problem(summary: object, evidence: list[Finding], rules: list[Rule]) -> str | None:
    """Return why an LLM summary is unusable, or None if it is safe to print."""
    if not isinstance(summary, str) or not summary.strip():
        return "missing"
    if len(summary) > MAX_SUMMARY_CHARS:
        return "too_long"
    codes = {f.icd10 for f in evidence}
    if any(code not in codes for code in ICD_TOKEN.findall(summary)):
        return "unknown_code"
    grounded = " ".join(f"{f.condition} {f.quote}" for f in evidence)
    for rule in rules:
        if any(icd_matches(f.icd10, p) for f in evidence for p in rule.icd10_prefixes):
            continue
        if any(_has_term(summary, t) and not _has_term(grounded, t) for t in rule.terms):
            return "unsupported_condition"
    return None


def _fallback_summary(decision: ExemptionDecision, evidence: list[Finding]) -> str:
    items = "; ".join(dict.fromkeys(f"{_one_line(f.condition)} ({f.icd10})" for f in evidence))
    window = f"the {decision.lookback_months}-month lookback ending {decision.as_of.isoformat()}"
    if decision.outcome == DecisionOutcome.EXEMPT:
        return f"The medical record documents {items} within {window}."
    return f"The medical record documents {items} within {window}; the diagnosis is not confirmed."


def _llm_summary(decision: ExemptionDecision, evidence: list[Finding], llm: LLMClient) -> str:
    data = "\n".join(f"{f.icd10} | {f.condition} | {f.quote}" for f in evidence)
    try:
        reply = llm.complete_json(task=LLM_TASK, instructions=INSTRUCTIONS, untrusted_text=data)
    except LLMError:
        reply = None
    summary = reply.get("summary") if isinstance(reply, dict) else None
    problem = _summary_problem(summary, evidence, _vocabulary().rules)
    if problem:
        log.info("statement summary fallback member=%s reason=%s", decision.member_id, problem)
        return _fallback_summary(decision, evidence)
    return _one_line(summary)


def _listed(lines: list[str], noun: str) -> list[str]:
    extra = len(lines) - MAX_LISTED
    return lines[:MAX_LISTED] + ([f"  ... and {extra} more {noun}(s)"] if extra > 0 else [])


def draft_statement(decision: ExemptionDecision, bundle: FindingsBundle, member: Member, llm: LLMClient) -> str:
    """ExemptionDecision + FindingsBundle + Member -> plain-text statement draft (<= 5000 chars).

    Raises ValueError for NOT_EXEMPT decisions, mismatched members, or evidence missing from the bundle.
    """
    if decision.outcome == DecisionOutcome.NOT_EXEMPT:
        raise ValueError("no statement for a NOT_EXEMPT decision")
    if not decision.member_id == bundle.member_id == member.member_id:
        raise ValueError("decision, bundle and member must be for the same member")
    evidence = _evidence(decision, bundle)
    labels = {r.rule_id: r.label for r in _vocabulary().rules}
    exempt = decision.outcome == DecisionOutcome.EXEMPT

    evidence_lines = [f'  - {f.icd10} — {_one_line(f.condition)} — "{_one_line(f.quote, MAX_QUOTE_CHARS)}" '
                      f"({f.note_id}, {f.note_date.isoformat()})" for f in evidence]
    if exempt:
        criteria_title = "Matched criteria:"
        criteria = [f"  - {m.rule_id}: {labels.get(m.rule_id, m.category)} ({m.category})"
                    for m in decision.matched_rules]
    else:
        criteria_title = "Possible criteria (a clinician must confirm):"
        criteria = [f"  - {_one_line(r)}" for r in decision.review_reasons]

    parts = [
        "MEDICAL FRAILTY STATEMENT — DRAFT" + ("" if exempt else " (NEEDS CLINICIAN REVIEW)"),
        f"Member: {_one_line(member.display_name)} ({member.member_id})",
        f"As of: {decision.as_of.isoformat()} | Lookback: {decision.lookback_months} months | "
        f"Rules: {decision.rules_version}",
        "",
        "Evidence from the medical record:",
        *_listed(evidence_lines, "finding"),
        "",
        criteria_title,
        *_listed(criteria, "item"),
        "",
        "Clinical summary:",
        _llm_summary(decision, evidence, llm),
    ]
    closing = "\n".join([
        "",
        "Clinician attestation:",
        "I have reviewed the evidence above against the patient's medical record.",
        "Clinician name: ________________   Credentials / NPI: ________________",
        "Signature: ________________   Date: ________________",
        "",
        SIGN_OFF,
        DISCLAIMER,
    ])
    body = "\n".join(parts)
    room = MAX_STATEMENT_CHARS - len(closing) - 2
    if len(body) > room:                     # never cut the attestation or sign-off; shorten the middle
        body = body[: room - 1] + "…"
    return body + "\n" + closing
