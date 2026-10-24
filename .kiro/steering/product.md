---
inclusion: always
---
# ProofKit: product

ProofKit helps the member and their clinic build a proof packet so that eligible MassHealth members keep their coverage. It organizes evidence; MassHealth decides.

## Problem
- From 2027-01-01, MassHealth ACA-expansion adults aged 19-64 must show, every month, 80 hours of work, school or community service, or income of at least $580 ($7.25 federal minimum wage x 80 h), or qualify for an exemption. Many must renew every 6 months.
- Current members are affected at their first 2027 renewal. New applicants must meet the requirement the month before they apply.
- The exemption in scope is medical frailty: for example schizophrenia, major depression, autoimmune disorder, heart or kidney failure, SUD, disabling mental disorders, and disabilities that impair activities of daily living. "denies depression", "r/o CHF" and "mother has lupus" never count.
- About 360,000 members face reporting. MassHealth expects about 175,000 to lose coverage. Most are eligible but can't produce the paperwork.
- The state's tools (Gainwell, CMS Emmy) serve the agency. Say "we couldn't find a member-side tool in Massachusetts", never "it doesn't exist".

## Users
| Persona | Needs from ProofKit |
|---|---|
| Member (often a gig worker or chronically ill) | Whether they are protected, what is missing and by when; one packet to submit; a short SMS reminder |
| Clinic (clinician or care team) | Conditions found in the notes, each quote highlighted in the note; a draft frailty statement to review and sign |
| Navigator (CHW or enrollment assister) | A status per member (PROTECTED / NEEDS_REVIEW / AT_RISK) and the next actions |

## Goals
1. A proof packet showing an exemption (medical frailty, grounded in note quotes) or compliance (>= 80 h or >= $580 a month from gig statements).
2. Every claim is auditable: each finding and earnings record traces back to an exact quote and offsets in its source.
3. Decisions are deterministic: the LLM extracts, tested rules code decides.
4. Prompt injection in notes and uploads has no effect (SYN-0005: only the ankle sprain; 30 h / $410, not 200 h / $5,000).
5. Deadlines and shortfalls in plain words: "$60 short in Feb 2027", plus the proof due date.

## Non-goals (do not build)
- Eligibility determinations, or wording that implies one.
- Submitting anything to MassHealth or integrating with state systems.
- Real PHI or PII. All data is synthetic (`SYN-####`).
- Medical advice, or diagnosing conditions the notes don't document.
- Exemptions other than medical frailty (caregiving, students, and so on).
- OCR of images. Images are flagged for review.

## Demo facts (fixtures)
- Demo date 2027-03-01, renewals 2027-03-20, verification month 2027-02, proof due 2027-03-06.
- SYN-0001 Maria: PROTECTED by exemption (lupus with nephritis).
- SYN-0002 James: PROTECTED by hours (92.5 h), NOT exempt (negation test).
- SYN-0003 Priya: PROTECTED by exemption (recurrent severe MDD; the old PTSD note is outside the lookback).
- SYN-0004 Dev: AT_RISK, $520 in Feb 2027, $60 short.
- SYN-0005 adversarial: AT_RISK; neither injection changes anything.

## Disclaimer
Show this exact text on every app page and in every proof packet:

> ProofKit helps people gather and organize evidence. It does not make eligibility determinations; MassHealth does.

`ProofKitStatus.disclaimer` has its own default in the frozen contracts. Do not edit the contracts to change it.
