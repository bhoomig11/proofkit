# Requirements: pdf-uploads

## Introduction
pypdf is bumped from 5.1.0 to 6.21.2, which fixes the advisories that made us turn PDF uploads off. This feature turns PDF uploads back on for the P2 wallet. It also makes sure PDFs can't get around the upload limits, and that the month split of long statements never loses or invents money or hours.

## Requirement 1: PDF is an allowed upload type
**User story:** As a member, I want to upload my earnings statement as a PDF, so that I don't have to convert it first.

Acceptance criteria:
1.1 WHEN the wallet loads `config/wallet_rules.json`, THE wallet SHALL include `pdf` in `allowed_doc_types`.
1.2 WHILE the installed pypdf is older than 6.21.2, THE wallet SHALL NOT include `pdf` in `allowed_doc_types`. (This is the existing test `test_pdf_uploads_off_while_pinned_pypdf_has_known_cves`.)

## Requirement 2: A PDF gives the same result as the same text
**User story:** As a member, I want my PDF statement to count exactly like the same statement pasted as text.

Acceptance criteria:
2.1 WHEN a one-page PDF holds the same text as a text statement, THE wallet SHALL report the same total hours, total income, qualifies flag, basis and needs_review for each month.
2.2 WHEN text comes from a PDF, THE wallet SHALL apply the same grounding, injection and date checks used for text documents.
2.3 THE wallet SHALL extract PDF text in memory only, and SHALL NOT read `filename`.

## Requirement 3: Hostile PDFs are rejected
**User story:** As an operator, I want hostile PDFs rejected, so that one upload can't exhaust memory or CPU.

Acceptance criteria:
3.1 IF a PDF stream would inflate past the decompression limit (for example 200 MB of zeros sent as about 200 KB), THEN THE wallet SHALL raise `ValueError` with a message that names the `doc_id`.
3.2 IF any document in a batch is rejected, THEN THE wallet SHALL make no LLM call for that batch.
3.3 IF a PDF has more pages than `max_pdf_pages`, is larger than `max_bytes`, is corrupt, is not valid base64, or arrives as `content_text`, THEN THE wallet SHALL raise `ValueError`.
3.4 WHEN the wallet rejects a document, THE error message SHALL contain the `doc_id` and SHALL NOT contain any document content.

## Requirement 4: The month split keeps every cent and every hour
**User story:** As a member with a quarterly or yearly statement, I want it spread across months without losing money or hours.

Acceptance criteria:
4.1 WHEN a statement covers more than 31 days, THE wallet SHALL split it into records that each lie inside one calendar month.
4.2 WHEN a statement is split, THE pieces SHALL be contiguous, SHALL NOT overlap, and SHALL cover the whole statement period.
4.3 WHEN a statement is split, THE piece incomes SHALL add up exactly to the source income, and the piece hours SHALL add up exactly to the source hours when hours were given.
4.4 WHEN a statement is split, EVERY piece SHALL keep the source quote.
4.5 IF a statement passes grounding, THEN THE wallet SHALL NOT drop it silently because of how the split rounds; no piece may come out negative.
4.6 Criteria 4.1 to 4.5 SHALL hold for both text/LLM and CSV statements.
