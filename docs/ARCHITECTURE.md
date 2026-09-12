# Architecture

## Golden path

```text
Browser -> Django upload API -> UploadedDocument + OCRJob -> Celery
        -> Response + DocumentPage grouping -> local preprocessing/page OCR
        -> response-level Answer aggregation
        -> review API/UI -> confirmed response -> CSV/XLSX export
```

The `QuestionnaireVersion` is the immutable schema boundary. A `ResponseBatch` always targets one version, so later template edits do not silently corrupt historical responses.

## Multi-page response boundary

```text
Questionnaire
  -> QuestionnaireVersion (expected page count + TemplatePages + Questions)
    -> ResponseBatch
      -> Response (one respondent)
        -> DocumentPages (physical pages)
        -> Answers (merged question/answer set)
```

`UploadedDocument` is the stored file and owns one background `OCRJob`. A PDF document may create several `DocumentPage` rows; a single image creates one. `DocumentPage` is deliberately also the response-page grouping record, avoiding a second model for the same physical page. It stores source PDF page number, original upload order, detected template page, assigned template page, classification method/confidence, page processing state and validation issues.

Grouping is independent of PaddleOCR/Tesseract. The upload path creates the response/page hierarchy first. Page OCR jobs then write engine-neutral text/regions. Deterministic classification may refine the provisional assignment using `Page X of Y` markers or similarity to stored `TemplatePage` text. The response aggregator acquires a row lock, waits for all document jobs belonging to the response to become terminal, fails the response when any page job fails, and only then rebuilds the response's answers from all logically ordered pages.

The same response boundary is used downstream: exporters write one row per confirmed `Response`, and Google Apps Script creates one source record per confirmed `Response`. Physical `DocumentPage` count is kept separately for OCR usage accounting.

## Billing and entitlement boundary

Plans are stored in relational tables and seeded through a data migration. Uploads reserve their page count atomically against the billable account before an OCR job is queued. Organization members share the owner's monthly allowance. XLSX and Bot Lab are enforced by the API, not only hidden in the frontend.

Paystack transactions are initialized by Django. Plan prices never come from the browser. Access is granted only after the backend verifies status, NGN amount, currency, and reference through Paystack or receives a valid HMAC-SHA512 signed webhook. Webhook payload hashes and payment references make fulfillment idempotent.

Bot Lab output is stored separately from human questionnaire responses and every exported row carries a synthetic-data label.

## Google Forms boundary

Apps Script jobs snapshot a confirmed human batch or a completed Bot Lab run, the questionnaire-to-Form title mapping, the target Form ID, and the generated code. The script runs in the user's Google account, uses `FormApp`, and never exposes Google credentials to ScanToForms. It previews mappings before submission, sends at most 40 responses per execution, and records submitted source IDs in Script Properties for rerun protection. Synthetic and human datasets retain different classifications.

## Security boundaries

- API querysets are owner-scoped; object IDs alone never authorize access.
- Uploads are signature checked, size/page limited, renamed with UUIDs, and served through an authenticated API endpoint.
- OCR happens outside request handling. Production workers should be isolated further with CPU/memory/time limits and malware scanning.
- Audit records are append-only through the public API.
- JWT access tokens are short lived; refresh-token rotation and blacklisting are enabled.
- Production settings require explicit trusted origins/hosts and enable secure cookie/HSTS defaults.

## OCR boundary

`documents.services.ocr` exposes an engine-neutral page result. PaddleOCR is tried first when available. Tesseract is the fallback. Preprocessing and questionnaire-specific mark/question mapping remain separately testable stages. Raw engine output is retained in JSON, while business data lives in relational models.

Page grouping does not call an OCR engine. It can consume normalized text produced by any engine after provisional grouping, so swapping PaddleOCR/Tesseract does not change ownership, batching or respondent boundaries.

## Deployment shape

The Compose environment represents the process boundaries: frontend, API, PostgreSQL, Redis, and worker. Uploaded files use a Django storage backend, allowing local storage to be swapped for S3-compatible storage without changing domain models.
