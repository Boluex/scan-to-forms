# Multi-page response grouping

## The domain rule

A physical page is not a respondent. A logical `Response` is one respondent's completed questionnaire and may contain several physical pages.

Example:

```text
Questionnaire: Student Housing Survey
Questions: 46
Expected pages per questionnaire: 4
Respondents: 50

Uploaded physical pages: 50 x 4 = 200
Logical responses: 50
CSV/XLSX rows: 50
Google Forms source records: 50
Billable OCR pages: 200
```

## Vocabulary and ownership

- `Questionnaire`: the research instrument owned by a user.
- `QuestionnaireVersion`: an immutable schema revision. It records `expected_page_count` and owns questions and template pages.
- `TemplatePage`: the known reference text/anchors for a page number in a version.
- `ResponseBatch`: a named collection of respondents using exactly one questionnaire version.
- `Response`: one logical respondent inside a batch. It snapshots the expected page count and owns the final merged answers.
- `UploadedDocument`: one stored PDF or image file and its OCR job.
- `DocumentPage`: one physical/source page linked to a response. This is the application's response-page entity.
- `Answer`: a question/value pair belonging to the logical response, not to the physical page. Its source metadata can identify the contributing response page.

Every API queryset involved in this hierarchy is owner-scoped. A page identifier does not give a different user access to its file, response or OCR text.

## What existed before multi-page grouping work

The original code already had questionnaire versions, response batches, responses, uploaded documents, per-page OCR results, answer confidence/review, exports and Apps Script generation. A multi-page PDF was rendered and OCRed page by page, and the upload created one response, so this common path already produced one export row.

The incomplete part was the relationship between several separate image documents and one respondent. `DocumentPage` did not carry a response assignment/template page number, expected page counts were not represented, and each document job could replace the response's whole answer set. There was no completeness/duplicate/order validation or manual page reassignment.

## Current grouping flow

```text
Upload intent and expected page count
  -> create/select logical Response
  -> create DocumentPage rows before OCR
  -> provisional deterministic grouping
  -> queue independent document/page OCR
  -> optional marker/template-text classification
  -> validate missing/duplicate/order/confidence/failure issues
  -> wait for all sibling jobs to finish
  -> merge all page regions in logical page order
  -> rebuild one Answer set on the Response
  -> human review and confirmation
  -> one export row / one Apps Script record
```

Grouping owns no OCR engine and works when the OCR implementation changes. Classification consumes engine-neutral page text when it is available.

## Upload modes

### One multi-page PDF per respondent

Each uploaded response PDF automatically creates one `Response`. PDF source pages become that response's `DocumentPage` rows. If the PDF page count equals the version's expected count, source order is accepted with high deterministic confidence. A three-page PDF for a four-page version is linked to one incomplete response and reports page 4 missing.

### Manual respondent

The frontend first creates a response, then exposes one upload slot for each expected page. Each uploaded image includes the response ID and explicit questionnaire page number. Manual assignments have full classification confidence. More respondents can be added without confusing their pages.

### Ordered bulk images

`POST /api/v1/response-batches/{batch_id}/prepare-bulk/` accepts `file_count`. It pre-creates the required responses and returns one upload assignment per file. With four expected pages, files 1–4 map provisionally to response 1, files 5–8 to response 2, and so on. Therefore 200 files produce 50 logical responses.

Ordered bulk grouping is not presented as intelligent recognition. Its assignment confidence is provisional until a reliable page marker/template match is found or a reviewer confirms the page manually.

## Page classification and validation

The deterministic classifier currently supports:

1. an explicit `Page X of Y` or `Page X/Y` marker whose total matches the version;
2. similarity between OCR-neutral page text and stored `TemplatePage.reference_text`, with a minimum score and separation from the second-best candidate;
3. manual reviewer assignment, which is authoritative;
4. upload order as a low-confidence fallback.

The model also reserves `QR_CODE` as a classification method so optional future IDs can be added without changing response ownership. QR generation/detection is not implemented now.

Validation reports structured issue codes, including:

- `MISSING_PAGES`
- `DUPLICATE_PAGES` / `DUPLICATE_PAGE`
- `DUPLICATE_FILE` for exact duplicate image hashes
- `OUT_OF_ORDER`
- `UNCLASSIFIED_PAGE`
- `PAGE_OUT_OF_RANGE`
- `PAGE_MISMATCH`
- `LOW_PAGE_CONFIDENCE`
- `PAGE_OCR_FAILED`

Confidently classified pages are displayed in logical questionnaire order while retaining `original_upload_order`. Duplicate or missing pages are never silently treated as complete. Response states reuse the project conventions: `UPLOADING`, `INCOMPLETE`, `READY_FOR_PROCESSING`, `PROCESSING`, `NEEDS_REVIEW`, `CONFIRMED`, `REJECTED` and `FAILED`.

## Manual corrections

The response review endpoint returns all pages and their issues with the merged answer list. The reviewer can change a page's questionnaire page number. A single-image document can also move to another response in the same batch; the old and new responses are both revalidated and re-aggregated. A source page inside a multi-page PDF cannot move independently because its stored file/OCR job is one document, but it can be renumbered.

Relevant endpoints:

```text
POST  /api/v1/responses/
GET   /api/v1/responses/?batch={batch_id}
GET   /api/v1/responses/{response_id}/
POST  /api/v1/response-batches/{batch_id}/prepare-bulk/
POST  /api/v1/documents/
GET   /api/v1/response-pages/{page_id}/
PATCH /api/v1/response-pages/{page_id}/
POST  /api/v1/responses/{response_id}/confirm/
```

Confirmation is blocked for incomplete, processing or failed responses and for unresolved page issues. This intentionally includes low-confidence provisional assignments until a reviewer confirms them manually; response-level informational warnings such as a safely corrected upload order do not block confirmation.

## Background jobs and race handling

One `UploadedDocument` has one `OCRJob`; a PDF job processes all of that document's source pages. Separate image uploads can therefore produce several sibling jobs for one response. Each job saves its terminal status before calling the response aggregator.

The aggregator locks the response row, checks every sibling job, and returns without creating a final answer set while any job is queued/processing. A failed sibling makes the response fail. Only after all jobs are terminal-success/review states does it combine regions in assigned questionnaire-page order and replace the response's answers once. This prevents the previous last-job-wins overwrite behavior.

## Export and Google Forms behavior

CSV/XLSX queries confirmed `Response` records and writes one row per response. It never writes one row per `DocumentPage`.

Google Apps Script source generation follows the same boundary. It serializes each confirmed response once, with all answers already merged across pages; its submission loop calls `form.createResponse()` and `submit()` once per serialized response record.

## Usage accounting

OCR quota reservation still uses inspected physical `page_count` at upload time. Response count and physical page count are separately exposed on batches. For 50 four-page respondents, capacity is 50 responses and usage is 200 OCR pages.

## Honest limitations

- Page-marker/template-text classification depends on readable text; it is not a learned visual-layout model and has not yet been benchmarked on the private representative dataset.
- When no reliable signal exists, ordered uploads remain low-confidence and require manual verification.
- Exact duplicate-file detection catches identical uploaded image bytes, not visually equivalent rescans.
- Moving one source page out of a multi-page PDF is intentionally disallowed; upload individual images for that workflow.
- QR generation/detection, visual anchor/image-hash matching and an advanced drag-and-drop grouping board remain future work.
