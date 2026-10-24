# Requirements Document

## Introduction

The Proof Packet feature produces a single, self-contained, safe-to-share HTML document that summarizes a MassHealth member's eligibility evidence. The Renderer takes a `ProofKitStatus` (with its optional `ExemptionDecision` and `WalletResult`), the member's clinical notes, and the member's extraction findings, and renders an HTML Packet containing: the overall status, the monthly compliance table, the highlighted evidence quotes inside each clinical note, the clinician statement draft, the deadlines, and the disclaimer. Optionally the HTML Packet may be converted to PDF.

All member and document text is UNTRUSTED. The Packet MUST neutralize that content so it cannot execute as script, exfiltrate data, or break out of its intended text context when opened in a browser. The Renderer MUST also be deterministic so that the same inputs always produce the same bytes, which keeps the Packet testable and auditable.

## Glossary

- **Renderer**: The component that builds the HTML Proof Packet from a `ProofKitStatus`, the member's clinical notes, and the member's findings.
- **Packet**: The single self-contained HTML document produced by the Renderer. The term "Packet" refers to the full rendered output.
- **Member**: The subject of the Packet, modeled by `proofkit.contracts.models.Member`. Carries `member_id`, `display_name`, `phone_last4`, and eligibility fields.
- **Note**: A single clinical note, modeled by `ClinicalNote`. Carries `note_id`, `text`, and metadata. `Note.text` is UNTRUSTED.
- **Finding**: An extracted evidence item, modeled by `Finding`. Carries `finding_id`, `note_id`, `condition`, `icd10`, `status`, `quote`, `quote_start`, and `quote_end`. A single Note may be referenced by SEVERAL Findings.
- **EarningsRecord**: An extracted earnings item, modeled by `EarningsRecord`. Carries `source_quote` and `platform` fields, both of which are UNTRUSTED.
- **Evidence Quote**: The exact substring of a Note identified by a Finding, located by the half-open offset range `[quote_start, quote_end)`.
- **Highlight Span**: A `[quote_start, quote_end)` offset range within a Note that the Renderer marks in the rendered Note text.
- **Merged Highlight Span**: A single contiguous highlighted region formed by combining Highlight Spans that overlap or are directly adjacent, rendered as one `<mark>` element rather than multiple nested or repeated marks.
- **Mark**: An HTML `<mark>` element produced by the Renderer around a Merged Highlight Span.
- **Status**: The `ProofKitStatus` instance supplied to the Renderer. Carries `status` (an `OverallStatus`), `protected_by`, `exemption`, `wallet`, `next_deadline`, `action_items`, and `disclaimer`.
- **OverallStatus**: The enum describing the member's state: `protected`, `at_risk`, or `needs_review`.
- **ExemptionDecision**: The `ExemptionDecision` carried by `Status.exemption`. Carries `statement_draft` and `review_reasons`.
- **WalletResult**: The `WalletResult` carried by `Status.wallet`. Carries `months`, `proof_due_date`, and `next_renewal_date`.
- **Monthly_Compliance**: A `MonthlyCompliance` row from `WalletResult.months`, carrying `month`, Decimal money and hours fields such as `total_income`, `total_hours`, `shortfall_income`, and `shortfall_hours`, the boolean `qualifies`, the `basis`, a `needs_review` flag, and `review_reasons`.
- **ActionItem**: An `ActionItem` from `Status.action_items`. Carries `title`, `detail`, and an optional `due`.
- **CSP**: The Content Security Policy declared by the Packet via a `<meta http-equiv="Content-Security-Policy">` element, which restricts the capabilities of the Packet when opened in a browser.
- **Escape**: HTML-escaping of text with `html.escape` so that `&`, `<`, `>`, `"`, and `'` are converted to their entity equivalents before the text is placed into HTML.
- **Renderer-authored markup**: HTML markup written by the Renderer itself, as opposed to markup that would originate from untrusted member or document text.
- **Deterministic Output**: Output that is byte-identical across runs for the same inputs, containing no timestamps, random identifiers, or other time- or run-dependent content.

## Requirements

### Requirement 1: Render a self-contained HTML Packet

**User Story:** As a care navigator, I want a single self-contained HTML Packet, so that I can review and share a member's eligibility evidence without any external dependencies.

#### Acceptance Criteria

1. WHEN the Renderer receives a `ProofKitStatus`, the member's Notes, and the member's Findings, THE Renderer SHALL produce a single HTML Packet string.
2. THE Packet SHALL embed all styles inline within the Packet and SHALL reference no external stylesheets, scripts, or fonts.
3. THE Packet SHALL include the overall status, the monthly compliance table, the highlighted evidence quotes, the clinician statement draft, the deadlines, and the disclaimer.
4. WHEN the Renderer is called with the default arguments `findings=None` and `notes=()`, THE Renderer SHALL return a valid Packet without raising an error.

### Requirement 2: Escape all untrusted member and document text

**User Story:** As a security reviewer, I want every piece of untrusted text escaped before it enters the Packet, so that member and document content cannot alter the Packet structure.

#### Acceptance Criteria

1. WHEN the Renderer places any of the following untrusted fields into the Packet, THE Renderer SHALL Escape that field: `Member.display_name`, `ClinicalNote.text`, `Finding.quote`, `EarningsRecord.source_quote`, `EarningsRecord.platform`, `ExemptionDecision.statement_draft`, `ExemptionDecision.review_reasons`, `MonthlyCompliance.review_reasons`, `ActionItem.title`, and `ActionItem.detail`.
2. WHEN the Renderer Escapes any untrusted field, THE Renderer SHALL convert `<` to `&lt;`, `>` to `&gt;`, and `&` to `&amp;`.
3. WHEN the Renderer places `EarningsRecord.source_quote` into the Packet, THE Renderer SHALL Escape the `source_quote`.
4. WHEN the Renderer places `EarningsRecord.platform` into the Packet, THE Renderer SHALL Escape the `platform`.

### Requirement 3: Render a non-executable script tag from untrusted input

**User Story:** As a security reviewer, I want untrusted text containing a script tag rendered as inert escaped text, so that member and document content can never execute as script in the Packet. THIS IS THE HIGHEST-PRIORITY REQUIREMENT OF THE FEATURE.

#### Acceptance Criteria

1. WHEN a `ClinicalNote`'s `text` contains the substring `<script>`, THE Renderer SHALL emit `&lt;script&gt;` in the Packet in place of an executable `<script>` element.
2. WHEN a `Finding`'s `quote` contains the substring `<script>`, THE Renderer SHALL emit `&lt;script&gt;` in the Packet in place of an executable `<script>` element.
3. WHEN an `EarningsRecord`'s `source_quote` contains the substring `<script>`, THE Renderer SHALL emit `&lt;script&gt;` in the Packet in place of an executable `<script>` element.
4. THE Packet SHALL contain no `<script>` element at all.

### Requirement 4: Render the clinician statement and deadlines

**User Story:** As a clinician, I want the statement draft and deadlines shown in the Packet, so that the reviewer has the supporting narrative and the dates that matter.

#### Acceptance Criteria

1. WHERE the Status carries an `ExemptionDecision` with a `statement_draft`, THE Renderer SHALL Escape the `statement_draft` and include the escaped statement in the Packet.
2. WHERE the Status carries an `ExemptionDecision` with a non-empty `review_reasons`, THE Renderer SHALL Escape each `review_reasons` entry and include each escaped entry in the Packet.
3. IF `Status.exemption` is None, THEN THE Renderer SHALL render the Packet without a statement section and without raising an error.
4. WHERE the Status carries a `next_deadline`, THE Renderer SHALL render the `next_deadline` date in ISO `YYYY-MM-DD` format.
5. WHERE the Status carries a `WalletResult`, THE Renderer SHALL render the `proof_due_date` in ISO `YYYY-MM-DD` format.
6. WHERE the Status carries a `WalletResult`, THE Renderer SHALL render the `next_renewal_date` in ISO `YYYY-MM-DD` format.
7. WHERE the Status carries a non-empty `action_items`, THE Renderer SHALL render each `ActionItem` with its `title` Escaped and its `detail` Escaped.
8. WHERE an `ActionItem` carries a `due`, THE Renderer SHALL render the `ActionItem` `due` date in ISO `YYYY-MM-DD` format.
9. THE Renderer SHALL include the Status `disclaimer`, Escaped, in the Packet.

### Requirement 5: Highlight evidence quotes

**User Story:** As a reviewer, I want every evidence quote highlighted inside the clinical note, so that I can see exactly which text supports each finding.

#### Acceptance Criteria

1. WHEN the Renderer renders a Note, THE Renderer SHALL highlight every Evidence Quote whose Finding references that Note, processing the Highlight Spans in ascending `quote_start` order.
2. WHEN two or more Highlight Spans overlap or are directly adjacent, THE Renderer SHALL merge the overlapping or adjacent Highlight Spans into a single Merged Highlight Span rendered as one `<mark>` element, so that contiguous highlighted regions produce one Mark rather than nested or repeated Marks.
3. WHEN the Renderer renders a highlighted Note, THE Renderer SHALL split the Note text into the text slices before, inside, and after each Merged Highlight Span, SHALL Escape each text slice individually, and SHALL insert the highlight markup around the escaped inside slice, so that markup is never Escaped and quoted text is always Escaped.
4. IF a Finding's `quote_start` or `quote_end` falls outside the bounds of `Note.text`, OR IF `Note.text[quote_start:quote_end]` does not equal the Finding's `quote`, THEN THE Renderer SHALL render the Escaped quote alone without an offset-based Highlight Span.
5. WHEN a Finding's offsets or quote fail the validation in acceptance criterion 4, THE Renderer SHALL complete rendering of the Packet without raising an error.
6. IF a Finding’s note_id matches no Note in notes, THEN THE Renderer SHALL render the Escaped quote alone, labelled with its note_id, without raising an error.

### Requirement 6: Restrict Packet capabilities with a Content Security Policy

**User Story:** As a security reviewer, I want the Packet locked down with a strict Content Security Policy, so that the Packet cannot run scripts or reach the network.

#### Acceptance Criteria

1. THE Packet SHALL declare a CSP that is exactly `default-src 'none'; style-src 'unsafe-inline'; img-src data:`.
2. THE Packet SHALL NOT contain any inline event-handler attributes matching `on*=`, such as `onclick=` or `onload=`.
3. THE Packet SHALL NOT contain any `javascript:` URLs.
4. THE Packet SHALL contain no `<script>` element at all.

### Requirement 7: Render the overall status

**User Story:** As a reviewer, I want the overall status shown in plain words, so that I can understand the member's eligibility state at a glance.

#### Acceptance Criteria

1. WHEN the Status `status` is `protected`, THE Renderer SHALL render the overall status as the words "Protected".
2. WHEN the Status `status` is `at_risk`, THE Renderer SHALL render the overall status as the words "At risk".
3. WHEN the Status `status` is `needs_review`, THE Renderer SHALL render the overall status as the words "Needs review".
4. WHERE the Status carries a `protected_by` value, THE Renderer SHALL Escape the `protected_by` value before including the value in the Packet.

### Requirement 8: Render the monthly compliance table

**User Story:** As a reviewer, I want the monthly compliance figures rendered from exact Decimal values, so that the money and hours shown match the audited numbers.

#### Acceptance Criteria

1. WHERE the Status carries a `WalletResult`, THE Renderer SHALL render one table row per `Monthly_Compliance` in `WalletResult.months`, including the `month`, `total_hours`, `total_income`, `qualifies`, and `basis`.
2. WHEN the Renderer renders a money value, including `total_income` and `shortfall_income`, THE Renderer SHALL format the value from its Decimal value with exactly 2 decimal places, such as `$1,480.00`.
3. WHEN the Renderer renders an hours value, including `total_hours` and `shortfall_hours`, THE Renderer SHALL format the value from its Decimal value with exactly 2 decimal places, such as `92.50`.
4. THE Renderer SHALL render every money and hours value from its Decimal value and SHALL NOT convert a Decimal money or hours value to a float.
5. WHERE a `Monthly_Compliance` row has `needs_review` true, THE Renderer SHALL indicate the needs-review state for that row and SHALL Escape each `review_reasons` entry and include each escaped entry in that row.
6. IF `Status.wallet` is None, THEN THE Renderer SHALL render the Packet without a monthly table and without raising an error.
7. IF `WalletResult.months` is empty, THEN THE Renderer SHALL render the monthly section with no data rows and without raising an error.

### Requirement 9: Exclude restricted member identifiers

**User Story:** As a privacy reviewer, I want restricted member identifiers kept out of the Packet, so that a shared Packet exposes no more member identity than necessary.

#### Acceptance Criteria

1. THE Packet SHALL NOT include the Member's `phone_last4`.
2. THE Renderer SHALL include the Member's `display_name`, Escaped, as a member identifier in the Packet.
3. THE Renderer SHALL include the Member's `member_id` as a member identifier in the Packet.
4. THE Renderer SHALL include no Member identifiers in the Packet other than `display_name` and `member_id`.

### Requirement 10: Consume only contract models and public module APIs

**User Story:** As a maintainer, I want the Renderer to depend only on the contract models and public module APIs, so that the Renderer stays decoupled from the internals of the wallet and reasoning modules.

#### Acceptance Criteria

1. THE Renderer SHALL consume data only through `proofkit.contracts` models and the public `__init__` APIs of the wallet and reasoning modules.
2. THE Renderer SHALL NOT import from internal, non-`__init__`, modules of the wallet package.
3. THE Renderer SHALL NOT import from internal, non-`__init__`, modules of the reasoning package.

### Requirement 11: Produce deterministic output

**User Story:** As an auditor, I want the Packet to be reproducible, so that the same inputs always yield the same document for verification and testing.

#### Acceptance Criteria

1. WHEN the Renderer is given the same inputs, THE Renderer SHALL produce byte-identical output.
2. THE Packet SHALL NOT contain timestamps.
3. THE Packet SHALL NOT contain random identifiers.
4. THE Packet SHALL NOT contain any other content that varies between runs for the same inputs.

### Requirement 12: Verify Packet correctness with tests

**User Story:** As a maintainer, I want automated tests over the Renderer, so that highlighting, escaping, script-neutralization, and determinism stay correct as the code changes.

#### Acceptance Criteria

1. THE test suite SHALL locate the Renderer tests under `tests/integration/`.
2. THE test suite SHALL include a property-based test using Hypothesis that generates Notes and Findings and renders the Packet.
3. FOR ALL generated Notes and Findings, the HTML-unescaped text inside each `<mark>` SHALL equal exactly `Note.text[s:e]` for the corresponding Merged Highlight Span `[s, e)`, AND every valid Finding's `[quote_start, quote_end)` SHALL lie inside exactly one Merged Highlight Span.
4. THE test suite SHALL include a property-based test using Hypothesis that generates arbitrary text for `ClinicalNote` text and for `Finding` and `EarningsRecord` quote content and renders the Packet.
5. FOR ALL generated inputs, THE Packet SHALL contain no <script> element.
6. FOR ALL generated inputs, THE raw unescaped angle-bracket Note or quote text SHALL NOT appear outside Renderer-authored markup.
7. THE test suite SHALL include an example-based test in which a Note or quote contains `<script>` and SHALL assert that `&lt;script&gt;` appears in the Packet.
8. THE test suite SHALL include an example-based test that asserts the Packet declares the exact CSP from Requirement 6.
9. THE test suite SHALL include an example-based test that asserts the Packet is byte-identical across two renders of the same inputs.
