# Implementation Plan: Proof Packet

## Overview

Implement the Python Proof Packet renderer as a deterministic, side-effect-free HTML boundary in `src/proofkit/integration/packet.py` through a tightly scoped, approximately 25-minute red-green plan. Each implementation subtask starts with its focused failing test and then makes the minimum production change needed to pass. The plan covers the required example-driven slices and only design Properties 3, 5, 7, and 10; it does not claim exhaustive property coverage.

## Tasks

- [x] 1. Establish the secure HTML rendering boundary (approximately 4 minutes)
  - [x] 1.1 Implement highest-priority script neutralization test-first
    - First create failing examples in `tests/integration/test_packet_script_security.py` for `<script>` supplied through `ClinicalNote.text`, valid and standalone `Finding.quote` values, and `EarningsRecord.source_quote`; parse the result and require escaped visible text with no `script` element.
    - Cover the default `render_packet(member, status)` call and assert it returns one complete HTML document without external assets or an exception.
    - Then create `src/proofkit/integration/packet.py` with the designed Python signature, a single `html.escape(..., quote=True)` text boundary, fixed inline styles, the exact CSP declaration, and only the minimum note, finding, and wallet-record projection needed to make the security examples pass.
    - Keep every dynamic value in text-node positions and do not add file I/O, network access, clock reads, random values, generated identifiers, scripts, or URL-bearing markup.
    - _Requirements: 1.1, 1.2, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 6.1, 6.4, 12.7, 12.8_

  - [x] 1.2 Enforce exact CSP and no-active-content guarantees test-first
    - First create failing parser-based examples in `tests/integration/test_packet_capabilities.py` that distinguish untrusted text from authored markup and inspect actual elements and attributes.
    - Assert the CSP content is exactly `default-src 'none'; style-src 'unsafe-inline'; img-src data:`, styles remain inline, no external resource is referenced, no attribute name starts with `on`, no URL-valued attribute contains `javascript:`, and no `script` element exists for adversarial mixed-case and entity-looking input.
    - Then update only the fixed skeleton and centralized escaping paths in `packet.py` as needed; preserve untrusted payloads as escaped visible text rather than deleting or sanitizing them away.
    - _Requirements: 1.2, 2.1, 2.2, 3.4, 6.1, 6.2, 6.3, 6.4, 12.5, 12.6, 12.8_

- [x] 2. Implement evidence highlighting and safe fallbacks (approximately 5 minutes)
  - [x] 2.1 Implement sorted, merged evidence highlights test-first
    - First create failing examples in `tests/integration/test_packet_highlights.py` for disjoint, out-of-order, duplicate, nested, overlapping, and directly adjacent valid spans.
    - Use an independent interval oracle and an HTML parser to assert ascending output, one `<mark>` per merged span, no nested or adjacent marks, exact HTML-unescaped mark text, and containment of every valid source span in exactly one merged span.
    - Then implement the private immutable planning records and focused span validation, sorting, merging, and raw-text slicing helpers from the design; slice the original note before escaping each outside and inside fragment, then insert only renderer-authored `<mark>` tags.
    - Preserve supplied note order and use original finding ordinal only as the deterministic tie-breaker for equal span coordinates.
    - _Requirements: 5.1, 5.2, 5.3, 12.2, 12.3_

  - [x] 2.2 Implement invalid-offset and missing-note fallbacks test-first
    - First create failing examples in `tests/integration/test_packet_fallbacks.py` for an end beyond the note, a start at or beyond the note length, an in-bounds exact-substring mismatch, and a `note_id` absent from the supplied notes.
    - Assert rendering never raises, never guesses or relocates a span, emits each escaped quote as standalone evidence without an offset-derived mark, and includes the escaped `note_id` label only for missing-note evidence.
    - Then implement deterministic same-note and missing-note fallback paths in `packet.py`, preserving original finding order and avoiding duplicate evidence output.
    - _Requirements: 5.4, 5.5, 5.6_

- [x] 4. Implement the packet presentation sections (approximately 8 minutes)
  - [x] 4.1 Implement overall status and privacy-minimized identity test-first
    - First create failing examples in `tests/integration/test_packet_status_privacy.py` for all three `OverallStatus` values, escaped `protected_by`, and independently distinguishable member-field sentinels.
    - Assert the labels are exactly `Protected`, `At risk`, and `Needs review`; include only escaped `display_name` and `member_id` as member identifiers; and prove `phone_last4` and every other member field are absent from identity output.
    - Then implement the fixed status-label mapping and member/status section without dumping, representing, or generically iterating a contract model.
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 9.1, 9.2, 9.3, 9.4_

  - [x] 4.2 Implement monthly compliance and wallet evidence test-first
    - First create failing examples in `tests/integration/test_packet_wallet.py` for no wallet, an empty months list, multiple ordered rows, review reasons, zero, one-cent, fractional-hours, grouped, and contract-boundary Decimal values.
    - Assert one row per month in source order; required month, hours, income, qualification, basis, shortfall, and review fields; exactly two decimal places; direct Decimal grouping; and no float artifacts.
    - Cover escaped `EarningsRecord.platform` and `source_quote` in ordered wallet evidence, including adversarial text, while avoiding duplicate record output from the initial security slice.
    - Then implement Decimal-only money/hours formatters and the wallet, month-row, and earnings-record renderers; omit the table for `wallet=None` but retain headers and an empty `<tbody>` when `months` is empty.
    - _Requirements: 2.1, 2.3, 2.4, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 4.3 Implement statement, deadline, action, and disclaimer rendering test-first
    - First create failing examples in `tests/integration/test_packet_statement_deadlines.py` for absent exemption, absent statement draft, non-empty exemption review reasons, every supported deadline, actions with and without due dates, and adversarial narrative text.
    - Assert statement/reason/title/detail/disclaimer text is escaped, `status.next_deadline`, wallet due and renewal dates, and action due dates use exact `date.isoformat()` output, and absent optional values do not invent content or raise.
    - Then implement the exemption and deadline/action helpers, place wallet dates in one canonical location, preserve contract-list order, and always include the escaped disclaimer.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [x] 4.4 Assemble a complete deterministic packet test-first
    - First create a fully populated representative example in `tests/integration/test_packet_complete.py` and assert the required fixed section order, all required packet content, exactly one complete document, and no duplicate canonical fields.
    - Add examples for default arguments and allowed optional omissions, then render the same input twice and assert equal strings and equal UTF-8 bytes.
    - Then wire all focused renderers into `render_packet` with list-and-join assembly, fixed `\n` separators, stable sequence traversal, and no unordered collection iteration for output.
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 4.3, 8.6, 8.7, 11.1, 11.2, 11.3, 11.4, 12.9_

- [x] 6. Add the focused property suite (approximately 5 minutes)
  - [x] 6.1 Implement Properties 3, 5, 7, and 10 in one test file
    - First create exactly `tests/integration/test_packet_properties.py` for the property suite, with all Hypothesis strategies, independent interval-merging logic, and a small `HTMLParser` oracle in that same file; create no separate support module or additional property-test file.
    - Configure each property with `@settings(max_examples=100)` and initially run the focused file against the public `render_packet` boundary.
    - For **Property 3: Capability confinement under arbitrary input**, generate adversarial text and assert no `script` element, the exact CSP `default-src 'none'; style-src 'unsafe-inline'; img-src data:`, no attribute whose name starts with `on`, no `javascript:` URL, and no external resource reference.
    - For **Property 5: Merged highlights exactly cover valid evidence**, derive valid findings from raw note slices, independently sort and merge their spans, and assert each parsed mark corresponds exactly to one merged span, its HTML-unescaped text equals `Note.text[s:e]`, and every valid finding span belongs to exactly one merged span.
    - For **Property 7: Missing-note evidence is preserved and labelled**, generate findings whose `note_id` is absent from all notes and assert rendering does not raise and includes the escaped quote plus the escaped `note_id` label without an offset-derived mark.
    - For **Property 10: Rendering is byte-deterministic**, render identical generated inputs twice and assert equal strings and equal UTF-8 bytes.
    - Include the corresponding exact design-property traceability comments in the four tests, and do not add tests for any other design property in this time-boxed suite.
    - Then make only the minimum corrections to `packet.py` needed for these four initially failing properties to pass; do not weaken the generated assertions or create another test/support file.
    - _Requirements: 1.2, 3.4, 5.1, 5.2, 5.3, 5.6, 6.1, 6.2, 6.3, 6.4, 11.1, 11.2, 11.3, 11.4, 12.2, 12.3, 12.5, 12.6, 12.9_

- [x] 8. Complete integration and focused hardening (approximately 3 minutes)
  - [x] 8.1 Wire and harden the final public renderer against the scoped suite
    - First run all retained packet example tests and `tests/integration/test_packet_properties.py`; preserve each failure or Hypothesis counterexample as a focused failing regression in the relevant existing test file before changing production code.
    - Then make the minimum `packet.py` corrections needed to pass: route displayed dynamic strings through the centralized escaping boundary, highlights through the validated merge plan, Decimal/date values through typed formatters, and optional sections through explicit total branches.
    - Remove interim duplicate rendering paths or orphaned helpers so `render_packet` is the single integrated entry point while retaining the exact CSP, deterministic order, contract-only inputs, and safe fallback behavior.
    - Validate the targeted packet suite and the repository's standard non-live tests and static checks without adding architecture/static-analysis tasks or new property files.
    - _Requirements: 1.1, 1.3, 2.1, 3.4, 4.9, 5.1, 5.4, 5.6, 6.1, 7.1, 8.1, 8.4, 9.1, 10.1, 10.2, 10.3, 11.1, 12.1, 12.2, 12.4_

## Notes

- The implementation language is Python, as specified by the approved design.
- This is an approximately 25-minute implementation time box: about 4 minutes for the secure boundary, 5 minutes for evidence handling, 8 minutes for presentation, 5 minutes for the focused property suite, and 3 minutes for integration hardening.
- Every implementation subtask preserves red-green order: write and run the focused failing test first, then make the minimum production change needed to pass it.
- Property-based testing is intentionally narrow rather than exhaustive: one `tests/integration/test_packet_properties.py` file covers only design Properties 3, 5, 7, and 10 with 100 examples per property and in-file strategies/oracles.
- Tests remain mandatory because the retained requirements make automated security, highlighting, fallback, and determinism verification part of this scoped feature plan.
- Production changes remain limited to `src/proofkit/integration/packet.py`; the plan adds no checkpoints, architecture/static-analysis tasks, property support module, or extra property-test files.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["2.1"] },
    { "id": 3, "tasks": ["2.2"] },
    { "id": 4, "tasks": ["4.1"] },
    { "id": 5, "tasks": ["4.2"] },
    { "id": 6, "tasks": ["4.3"] },
    { "id": 7, "tasks": ["4.4"] },
    { "id": 8, "tasks": ["6.1"] },
    { "id": 9, "tasks": ["8.1"] }
  ]
}
```
