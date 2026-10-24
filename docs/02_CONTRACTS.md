# 02: Contracts (FROZEN)

The single source of truth is `src/proofkit/contracts/models.py`. This page explains it. If the two disagree, the code wins.

## Data flow
```
ClinicalNote[] ──P1A──▶ FindingsBundle ──P1B──▶ ExemptionDecision ─┐
                                                                   ├─FINAL─▶ ProofKitStatus
EarningsDocument[] ──P2──▶ EarningsRecord[] ──P2──▶ WalletResult ──┘
```

## Global rules baked into the models
- Every model has `extra="forbid"` (unknown fields are rejected) and `frozen=True` (immutable).
- `member_id` must match `SYN-\d{4}`. The code accepts only synthetic data.
- Money and hours are `Decimal`. In JSON, write them as strings (`"598.20"`).
- ICD-10 codes are uppercase with a dot: `M32.14`, `F33.2`, `S93.401A`.

## Model notes
| Model | Key invariants |
|---|---|
| `Finding` | `quote_end - quote_start == len(quote)`, and the quote must equal `note.text[quote_start:quote_end]` (the contract test checks the golden data; P1A guarantees it for real output). `status` uses the 6-value enum. |
| `FindingsBundle` | `dropped_ungrounded` counts findings dropped for any safety reason. |
| `ExemptionDecision` | EXEMPT ⇒ an exemption type, matched rules, and evidence. NOT_EXEMPT ⇒ type `none`. NEEDS_CLINICIAN_REVIEW ⇒ at least one `review_reasons`. |
| `EarningsDocument` | Exactly one of `content_text` / `content_b64`. `filename` is display-only. |
| `EarningsRecord` | Covers at most 31 days. `hours` is optional (Upwork has none). `source_quote` is the exact source text. |
| `MonthlyCompliance` | `qualifies ⇔ basis != none`. Shortfalls are ≥ 0. |
| `ProofKitStatus` | Always carries the disclaimer. |

## LLM task payloads (between your module and `LLMClient`; owned by each module)
| task | Owner | Expected JSON |
|---|---|---|
| `extract_findings` | P1A | `{"findings":[{"condition","icd10","status","quote","quote_start","quote_end","confidence"}]}` |
| `draft_statement` | P1B | `{"summary": str}` |
| `extract_earnings` | P2 | `{"records":[{"platform","period_start","period_end","hours","gross_income","source_quote","confidence"}]}` |

These task payloads are module-internal: the owner may change them, as long as their `FakeLLM` tests change at the same time. FINAL's `RoutingLLM` in `tests/integration` routes by task name only.
