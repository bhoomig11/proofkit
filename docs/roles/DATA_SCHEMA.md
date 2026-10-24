# ProofKit data schema

One page that shows every data object in ProofKit, where it lives, who owns it, and how it connects.
The source of truth is `src/proofkit/contracts/models.py`. If this page and the code disagree, the code wins.

## 1. The big picture

There are three layers. Data only flows left to right.

```mermaid
flowchart LR
  subgraph BUILD["A. Dataset build (outside this repo)"]
    S[Synthea patients] --> P[personas]
    S --> T[note truth]
    T --> W[note writer]
    W --> V[validator]
  end
  subgraph REPO["B. Files in this repo"]
    FX["fixtures/*.json"]
    CF["config/*.json"]
  end
  subgraph RUN["C. App at runtime (contract models)"]
    IN["Member, ClinicalNote, EarningsDocument"] --> OUT["FindingsBundle, ExemptionDecision, WalletResult"]
    OUT --> ST[ProofKitStatus]
  end
  V -- "exports notes + answer keys" --> FX
  FX -- "tests load" --> IN
  CF -- "rules" --> OUT
```

- **A** makes synthetic test data. Nothing in A is imported by the app.
- **B** is what the app and the tests read: fixture files shaped exactly like the contract models, plus rule configs.
- **C** is the running app. Modules talk to each other only through the contract models.

## 2. Runtime flow (who calls what)

```mermaid
flowchart TD
  M[Member] --> RUNM["run_member (FINAL)"]
  N["ClinicalNote[]"] --> EX["extract_findings (P1A)"]
  D["EarningsDocument[]"] --> BW["build_wallet (P2)"]
  EX --> FB[FindingsBundle]
  FB --> DE["decide_exemption (P1B)"]
  FR[(config/frailty_rules.json)] --> DE
  DE --> ED[ExemptionDecision]
  WR[(config/wallet_rules.json)] --> BW
  BW --> WRS[WalletResult]
  ED --> BS["build_status (FINAL)"]
  WRS --> BS
  M --> BS
  BS --> PS[ProofKitStatus]
  RUNM -. orchestrates .-> EX
  RUNM -. orchestrates .-> DE
  RUNM -. orchestrates .-> BW
  RUNM -. orchestrates .-> BS
```

| Function | Owner | Takes | Returns |
|---|---|---|---|
| `extract_findings(notes, member_id, llm)` | P1A | `ClinicalNote[]` | `FindingsBundle` |
| `decide_exemption(bundle, member, rules, as_of)` | P1B | `FindingsBundle`, `Member`, `FrailtyRules`, date | `ExemptionDecision` (no LLM, deterministic) |
| `draft_statement(decision, bundle, member, llm)` | P1B | `ExemptionDecision`, `FindingsBundle` | `str` (goes into `statement_draft`) |
| `build_wallet(member, docs, llm, rules, today)` | P2 | `EarningsDocument[]` | `WalletResult` |
| `parse_documents` / `evaluate_months` / `compute_deadlines` | P2 | documents / records / member | `EarningsRecord[]` / `MonthlyCompliance[]` / deadlines |
| `build_status(member, exemption, wallet, today)` | FINAL | the two results | `ProofKitStatus` |
| `run_member(member, notes, docs, llm, ...)` | FINAL | everything | `ProofKitStatus` |

## 3. Contract models and how they connect

`PK` = primary key, `FK` = points to another object. All models are immutable and reject unknown fields.

```mermaid
erDiagram
  MEMBER ||--o{ CLINICAL_NOTE : "member_id"
  MEMBER ||--o{ EARNINGS_DOCUMENT : "member_id"
  MEMBER ||--|| FINDINGS_BUNDLE : "member_id"
  FINDINGS_BUNDLE ||--o{ FINDING : "findings"
  CLINICAL_NOTE ||--o{ FINDING : "note_id"
  FINDINGS_BUNDLE ||--|| EXEMPTION_DECISION : "decide_exemption"
  EXEMPTION_DECISION ||--o{ MATCHED_RULE : "matched_rules"
  MATCHED_RULE }o--|| FRAILTY_RULE : "rule_id"
  MATCHED_RULE }o--|{ FINDING : "finding_ids"
  EARNINGS_DOCUMENT ||--o{ EARNINGS_RECORD : "source_doc_id"
  WALLET_RESULT ||--o{ EARNINGS_RECORD : "records"
  WALLET_RESULT ||--o{ MONTHLY_COMPLIANCE : "months"
  MONTHLY_COMPLIANCE }o--o{ EARNINGS_RECORD : "record_ids"
  MONTHLY_COMPLIANCE }o--|| WALLET_RULES : "thresholds"
  MEMBER ||--|| PROOFKIT_STATUS : "member_id"
  PROOFKIT_STATUS |o--o| EXEMPTION_DECISION : "exemption"
  PROOFKIT_STATUS |o--o| WALLET_RESULT : "wallet"
  PROOFKIT_STATUS ||--o{ ACTION_ITEM : "action_items"

  MEMBER {
    string member_id PK "SYN-0001 format only"
    string display_name "synthetic"
    string eligibility_group "expansion_adult"
    date renewal_date
    string phone_last4 "optional"
  }
  CLINICAL_NOTE {
    string note_id PK "N-0001-a"
    string member_id FK
    date note_date
    string author_role
    string text "UNTRUSTED, max 50k chars"
  }
  FINDINGS_BUNDLE {
    string member_id FK
    list notes_processed "note_ids read"
    list findings
    int dropped_ungrounded
    string extractor_version
  }
  FINDING {
    string finding_id PK "F-N-0001-a-0"
    string note_id FK
    date note_date
    string condition
    string icd10 "M32.14 format"
    enum status "6 values"
    string quote "exact substring of note"
    int quote_start
    int quote_end
    float confidence
  }
  EXEMPTION_DECISION {
    string member_id FK
    enum outcome "exempt, not_exempt, needs_clinician_review"
    enum exemption_type
    float confidence
    list matched_rules
    list evidence_finding_ids FK
    int lookback_months
    date as_of
    string rules_version
    list review_reasons
    string statement_draft "optional"
  }
  MATCHED_RULE {
    string rule_id FK
    string category
    list finding_ids FK
    string rationale
  }
  FRAILTY_RULE {
    string rule_id PK "config, MF-AI-01"
    string category
    list icd10_prefixes
  }
  EARNINGS_DOCUMENT {
    string doc_id PK
    string member_id FK
    string filename "display only"
    enum doc_type "text, csv, pdf, image"
    string content_text "UNTRUSTED, or"
    string content_b64 "UNTRUSTED, one of the two"
  }
  EARNINGS_RECORD {
    string record_id PK
    string member_id FK
    string source_doc_id FK
    string platform
    date period_start
    date period_end "max 31 days"
    decimal hours "optional"
    decimal gross_income
    string source_quote
    float confidence
  }
  MONTHLY_COMPLIANCE {
    string month PK "YYYY-MM"
    decimal total_hours
    bool hours_known_for_all_records
    decimal total_income
    bool qualifies
    enum basis "hours, income, averaged_income, none"
    decimal shortfall_hours
    decimal shortfall_income
    list record_ids FK
  }
  WALLET_RULES {
    decimal monthly_hours_required "80"
    decimal monthly_income_required "580.00"
    int verification_months_before_renewal
  }
  WALLET_RESULT {
    string member_id FK
    list records
    list months
    list verification_months
    date next_renewal_date
    date proof_due_date
    string rules_version
  }
  PROOFKIT_STATUS {
    string member_id FK
    enum status "protected, at_risk, needs_review"
    string protected_by "exemption:TYPE or compliance:BASIS"
    date next_deadline
    string disclaimer
  }
  ACTION_ITEM {
    int priority "1 to 5"
    string title
    string detail
    date due
  }
```

### Keys at a glance

| Key | Format | Defined in | Used by |
|---|---|---|---|
| `member_id` | `SYN-0001` (regex `^SYN-\d{4}$`) | `Member` | every model that belongs to a person |
| `note_id` | `N-0001-a` (member number + letter) | `ClinicalNote` | `Finding.note_id`, `FindingsBundle.notes_processed` |
| `finding_id` | `F-{note_id}-{i}`, i in quote order | `Finding` | `MatchedRule.finding_ids`, `ExemptionDecision.evidence_finding_ids` |
| `rule_id` | `MF-AI-01` | `config/frailty_rules.json` | `MatchedRule.rule_id` |
| `doc_id` | `D-0001-dd-jan` | `EarningsDocument` | `EarningsRecord.source_doc_id` |
| `record_id` | free text | `EarningsRecord` | `MonthlyCompliance.record_ids` |
| `month` | `YYYY-MM` | `MonthlyCompliance` | `WalletResult.verification_months` |

### Value rules

- `Finding.status` is one of `current`, `historical`, `ruled_out`, `negated`, `family_history`, `uncertain`.
- `Finding.icd10` is uppercase with a dot (`M32.14`). Family and past history use the **condition's own code**; the status says whose it is or when. Mother's breast cancer = `C50.919` + `family_history`, not `Z80.3`.
- A named denied symptom is a finding: "Denies chest pain" = `R07.9` + `negated`.
- `quote` must equal `note.text[quote_start:quote_end]`.
- Money and hours are `Decimal`, written as strings in JSON (`"598.20"`). Dates are ISO (`2027-03-01`).
- Only `current` findings can count toward an exemption (`counted_statuses` in `frailty_rules.json`).

## 4. Files in this repo

| File | Shape | Owner | Read by |
|---|---|---|---|
| `fixtures/members/members.json` | `{demo_today, members: Member[]}` | unassigned | tests, app |
| `fixtures/members/expected_status.json` | `{member_id: {status, protected_by}}` | unassigned | integration tests |
| `fixtures/notes/{note_id}.json` | `ClinicalNote` | P1A | tests (`notes_by_member`) |
| `fixtures/findings/{member_id}.golden.json` | `FindingsBundle` (answer key) | P1A | P1A acceptance tests |
| `fixtures/decisions/expected.json` | `{as_of, lookback_months, expected: {member_id: {outcome, exemption_type, rule_ids, evidence_finding_ids}}}` | P1B | P1B acceptance tests |
| `fixtures/earnings_docs/{doc_id}.json` | `EarningsDocument` | P2 | tests (`earnings_docs_by_member`) |
| `fixtures/earnings/{member_id}.golden.json` | `EarningsRecord[]` (answer key) | P2 | P2 acceptance tests |
| `fixtures/wallet/expected.json` | `{member_id: {month: MonthlyCompliance subset}}` | P2 | P2 acceptance tests |
| `config/frailty_rules.json` | rule list, `lookback_months`, `counted_statuses` | P1B | `decide_exemption` |
| `config/wallet_rules.json` | thresholds, verification months, platforms | P2 | `build_wallet` |

How the fixture files point at each other for one member:

```mermaid
flowchart LR
  MJ["members.json<br/>SYN-0001"] --> NJ["notes/N-0001-a.json<br/>notes/N-0001-b.json"]
  NJ --> FG["findings/SYN-0001.golden.json<br/>F-N-0001-a-0 ..."]
  FG --> DX["decisions/expected.json<br/>evidence_finding_ids"]
  MJ --> EDJ["earnings_docs/D-0001-*.json"]
  EDJ --> EG["earnings/SYN-0001.golden.json<br/>source_doc_id"]
  EG --> WX["wallet/expected.json<br/>SYN-0001 by month"]
  DX --> ES["expected_status.json"]
  WX --> ES
```

## 5. Dataset build (outside this repo)

The extra synthetic personas are built in a separate folder (`proofkit-data/`) and exported into the
fixture files above. Only the export touches this repo.

```mermaid
erDiagram
  SYNTHEA_PATIENTS ||--o{ SYNTHEA_ENCOUNTERS : "patient_id"
  SYNTHEA_PATIENTS ||--o{ SYNTHEA_CONDITIONS : "patient_id"
  SYNTHEA_ENCOUNTERS ||--o{ SYNTHEA_CONDITIONS : "encounter_id"
  SYNTHEA_CONDITIONS }o--|| SNOMED_ICD10_MAP : "snomed_code"
  SYNTHEA_PATIENTS ||--|| PERSONAS : "patient_id"
  PERSONAS ||--o{ NOTE_PLAN : "member_id"
  SYNTHEA_ENCOUNTERS ||--o| NOTE_PLAN : "encounter_id"
  NOTE_PLAN ||--|| NOTE_TRUTH : "note_id"
  NOTE_TRUTH ||--|| NOTE_TEXT : "note_id"
  NOTE_TEXT ||--o{ NOTE_LABELS : "note_id"

  SYNTHEA_PATIENTS {
    uuid Id PK "patient_id"
    date BIRTHDATE
    string GENDER
    string FIRST
  }
  SYNTHEA_CONDITIONS {
    uuid PATIENT FK
    uuid ENCOUNTER FK
    date START
    date STOP "blank = active"
    int CODE FK "SNOMED"
  }
  SNOMED_ICD10_MAP {
    int snomed_code PK
    string icd10 "checked against CMS FY2027"
    bool qualifies "via frailty_rules.json"
  }
  PERSONAS {
    string member_id PK "SYN-0006 and up"
    uuid patient_id FK
    string scenario "S1 S3-S9, SEED"
    string expected_status
  }
  NOTE_PLAN {
    string note_id PK
    uuid encounter_id FK
    date note_date
  }
  NOTE_TRUTH {
    string note_id PK
    list items "required sentences + labels"
  }
  NOTE_TEXT {
    string note_id PK
    string text "becomes ClinicalNote"
  }
  NOTE_LABELS {
    string note_id FK
    string icd10
    string status
    int quote_start "becomes Finding"
  }
```

| Dataset table | Exported to repo as |
|---|---|
| `personas` + Synthea first name | `Member` rows in `fixtures/members/members.json` |
| `note_text` + `note_plan` | `fixtures/notes/{note_id}.json` (`ClinicalNote`) |
| `note_labels` | `fixtures/findings/{member_id}.golden.json` (`FindingsBundle`) |

`patient_id` (Synthea) never enters the repo. Inside the app a person is only ever a `member_id`.

Status: the 5 seed members `SYN-0001`..`SYN-0005` are in the repo now. Generated members `SYN-0006`
and up are being validated and are not exported yet.

## 6. Open decisions

- Impairment severity (mild vs severe) has no field in `Finding`. Out of scope for this hackathon.
- Gig platform names: real names in the fixtures vs invented names in the dataset spec (P2 to decide).
- `fixtures/members/` has no owner in `CLAUDE.md`.
- `MF-DD-01` lists F70-F73 but not F79 (unspecified intellectual disability) (P1B to decide).
