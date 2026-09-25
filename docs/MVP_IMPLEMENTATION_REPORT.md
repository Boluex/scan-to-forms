# ScanToForms focused MVP implementation report

Scope: two website services, manual bank transfer, operator fulfillment, controlled Render beta. This refactors the existing application; it does not replace its questionnaire, response, OCR, or script-generation architecture. No WhatsApp, Paystack checkout, Google OAuth, LLM, or external Google submission was added.

## 1. What existed before

The inspected baseline (`8704599`) contained Next.js/TypeScript, Django/DRF, PostgreSQL/Redis/Celery Compose services, PaddleOCR/Tesseract and OpenCV preprocessing, questionnaire versions/questions/options/templates, response batches and multi-page grouping, answer review, CSV/XLSX, Google Apps Script generation, deterministic Bot Lab generation, Paystack/subscription models, notifications and Django Admin. The original backend suite had 44 tests. Several workflows were only partial: there was no commercial order or manual-payment boundary, public navigation exposed a broad SaaS product, notifications were disconnected, ownership checks were inconsistent, regrouping could discard human corrections, final exports admitted unfinished responses, and spreadsheet formulas were not neutralized.

## 2. What changed

The customer workspace now centers on `/digitize`, `/synthetic`, `/orders`, `/notifications`, and `/account`. Orders snapshot server-side prices, validate upload completeness, collect bank-transfer claims, require staff verification, and gate processing and delivery. Operators prepare schemas, inspect pages and answers, associate internal generation results, check readiness, and release results. Existing records and models are retained. The local project database and existing Docker volumes were not reset or migrated during implementation; migrations run in disposable test databases and on future deployment.

## 3. Exact files changed

See the generated file inventory at the end of this report. It covers all changes from baseline, including earlier safety/order checkpoints, new frontend routes, migrations, tests, deployment files, and this report.

## 4. New models

- `Order`: human-readable `STF-000001` reference, owner, service, title/instructions, service-specific counts, expected pages, Google URL/ID, NGN total, pricing snapshot, manual payment claim and verifier metadata, commercial/processing timestamps, operator notes, and protected relationships to existing Questionnaire, ResponseBatch, BotRun and AppsScriptJob records.
- `OrderEvent`: append-only audit records with actor, event, previous/new status, note, metadata and timestamp. Operational services also write the existing AuditLog.
- Existing `UploadedDocument` gains an order relation and per-order idempotency key. `Answer` gains provenance. Existing response confirmation and order consistency rules receive database constraints.

## 5. New migrations

1. `questionnaires/0003_reviewed_answer_integrity`: provenance field/backfill, demotion of inconsistent legacy confirmations, and status/timestamp consistency constraint.
2. `orders/0001_initial`: Order and OrderEvent with service/payment consistency constraints and protected foreign keys.
3. `documents/0003_uploadeddocument_order_uploadeddocument_upload_key_and_more`: order association and unique order upload key.
4. `notifications/0002_alter_notification_kind`: payment/processing/attention/ready/rejection kinds.
5. `botlab/0002_alter_syntheticresponse_data_label`: canonical default SYNTHETIC TEST DATA label. Existing synthetic records remain separate and their supported export always includes the test-data label.

No data reset or destructive model removal is required. Back up real data before applying migrations, particularly because inconsistent old confirmations become review-required.

## 6. New API endpoints

All order endpoints live under `/api/v1/orders/`. Except `configuration/`, they require authentication and owner or staff access. `reference` is a human-readable order reference, not an authorization mechanism.

| Method / suffix | Purpose |
| --- | --- |
| GET `configuration/` | Public rates, service limits, processing mode and payment availability |
| POST root; GET root / `{reference}/` | Create, paginated list, retrieve |
| GET/POST `{reference}/uploads/` | Paginated upload metadata or validated upload; never queues OCR |
| DELETE `{reference}/uploads/{document_id}/` | Remove an unpaid upload |
| GET `{reference}/uploads/{document_id}/file/` | Owner-scoped original source file |
| POST `{reference}/submit/` | Validate completeness and proceed to bank instructions |
| POST `{reference}/payment-claim/` | Record I HAVE PAID; no unlock |
| POST `{reference}/verify-payment/`, `reject-payment/` | Staff verification or rejection with reason |
| POST `{reference}/process/` | Staff starts paid processing after schema verification |
| GET/POST `{reference}/schema/` | Staff inspects/prepares questionnaire schema |
| GET `{reference}/respondents/` | Paginated operational metadata, without answers |
| GET `{reference}/operator_detail/`; POST `note/` | Staff source links, readiness issues, audit trail and notes |
| POST `{reference}/manual-page-reviewed/` | Record real human inspection in manual mode |
| POST `{reference}/generate-synthetic/`, `attach-bot-run/` | Staff internal generation / completed result association |
| GET/POST `{reference}/synthetic-responses/` | Paginated staff inspection and typed answer corrections |
| POST `{reference}/prepare-script/`, `ready/`, `complete/` | Generate real-data script, release reviewed result, acknowledge receipt |
| GET `{reference}/script/` | Paid, released script; `?download=1` serves `.gs` |
| GET `{reference}/export/?file_format=csv` or `xlsx` | Paid, released final export; synthetic supports labelled CSV only |

Also added: `/api/v1/notifications/unread-count/` and `/health/`. Existing review, page-correction, retry, auth and notification mark-read endpoints are reused. Response lookup now supports a sequence filter for navigation across an entire batch.

## 7. New frontend routes

`/digitize`, `/synthetic`, `/orders`, `/orders/{reference}`, `/notifications`, `/account`, `/forgot-password`, `/reset-password`. `/` is rewritten around two services. `/dashboard` redirects to orders; retained `/dashboard/*` tools require staff in the frontend and at the API boundary. The existing `/dashboard/review/{id}?order=STF-...` provides paid-order operator review.

## 8. Hidden/deactivated features

Public subscription plans, page packs, organizations/teams, analytics, priority processing, checkout, public Bot Lab, legacy export/script dashboards, and old digitization navigation are removed from the customer flow. Legacy API access defaults off for non-staff. Legacy billing endpoints and checkout are blocked when `ENABLE_PAYSTACK=false`. Old models and useful staff tools remain. WhatsApp, Google OAuth/import/direct response API, chatbot and LLM features are not implemented or exposed. Synthetic Google submission is blocked rather than stripping classification.

## 9. Security fixes

Ownership filters and relationship validation cover questionnaire/version creation, batches, responses, answers, documents/pages, exports, BotRun, AppsScriptJob, orders and notifications. The cross-owner template-upload attachment flaw is rejected. Staff access is explicit; a missed nested staff check discovered in E2E was corrected. Customers cannot verify payment or use operator endpoints. Before release, legacy routes cannot bypass the commercial gates.

Logout blacklists only the caller's refresh token and clears browser tokens. Password-reset links target the new frontend, and changed passwords invalidate existing JWTs through the configured password check. Email verification cannot reactivate a suspended/deactivated account. Registration now rolls back creation if email delivery fails. Refresh attempts are coordinated across parallel frontend requests.

Corrupt image/PDF parsing produces validation errors. Upload keys cannot silently substitute different content. Files are scoped to their order/owner; private object-store downloads pass through authenticated endpoints. Docker build context excludes local databases, media and environment files. Django is updated within the 5.2 LTS line; the frontend PostCSS override resolves the npm audit findings.

## 10. Data-integrity fixes

Human/manual and approved answers survive reaggregation. Page movement, regrouping, deletion, retry and answer edits invalidate confirmation; status and confirmed_at cannot disagree at the database level. Released orders are revoked when reviewed source data changes. Final eligibility requires complete unique logical pages, completed processing, resolved blocking issues, exact questionnaire answer coverage, explicit approval/correction, and valid typed values. Final export and real-data Apps Script use only eligible confirmed responses. Every question must be mapped for an order script.

All spreadsheet paths sanitize formula prefixes in user-controlled headers and values. Synthetic rows retain a separate model/classification and labelled CSV; malformed rows block readiness. Duplicate worker delivery is claimed atomically, and successful OCR reaggregation refreshes machine answers while retaining human provenance. PostgreSQL testing also found and fixed an existing nullable-join row-lock error in retained billing code.

## 11. Payment workflow

`UPLOADING → AWAITING_PAYMENT → PAYMENT_SUBMITTED → PAID`. Price is calculated in Decimal on the server using configured rates and snapshotted on the order. I HAVE PAID stores sender/reference/time and leaves payment unverified. A staff member checks the bank statement independently and verifies the claim. Rejection requires a reason and returns the order to awaiting payment; claims, rejections and verification are audited. Payment does not start OCR automatically: the operator verifies the schema and starts processing. There is no bank API, refund automation, or Paystack charge.

## 12. Digitization workflow

Create counts/schema draft → upload completed respondent pages → validate counts → bank claim → staff verification → verified schema → real Celery OCR or explicitly manual transcription → page/answer review → respondent confirmation → complete Google title mapping → Apps Script preparation → READY → authenticated delivery.

Ordered images are assigned to known consecutive respondent/page slots. Phone capture names the respondent and page explicitly and advances after upload. PDF upload is one complete PDF per respondent. A blank template is optional and is separate from completed responses. Arbitrarily shuffled respondents are not supported. The 480-page representation test verifies 120 logical responses with four pages each and all six pages of respondent pagination. It is not a 480-page OCR throughput benchmark.

Original source files and operational metadata are visible before payment; extracted answers and results are not. No OCR job is created by upload. Missing pages, duplicate files, invalid page assignments and unresolved answers block release. Upload and operator throttles are separated from small legacy upload limits. The browser loads paginated metadata and only the selected respondent page preview, not hundreds of full-resolution images.

## 13. Synthetic workflow

One blank multi-page questionnaire plus a requested response count creates a SYNTHETIC_DATA order, with no human response batch. After staff payment verification and schema preparation, an operator runs the existing deterministic generator or attaches a matching completed BotRun owned by the customer. Staff inspect paginated rows, correct JSON answers when needed, and release labelled CSV only after count/classification/content checks pass. Instructions are for human fulfillment; no LLM interpretation or guaranteed turnaround is promised. Complex schemas or generator failures still need operator intervention.

## 14. Apps Script workflow

An operator maps every questionnaire key to an exact existing Google Form item title. The existing generator and its previewMapping/startSubmission/continueSubmission/submissionStatus functions are preserved. The customer receives COPY CODE and `.gs` download only after verified payment and READY/COMPLETED eligibility. Instructions include all twelve requested steps and warn that Google may request authorization during mapping preview.

The form must already exist. There is no Google OAuth connection, password collection, ownership verification, automatic import, direct Forms API creation, or server-side response submission. Standard HTTPS edit URLs/IDs are accepted; published `/d/e/` and short links are clearly rejected. Mapping is checked by Google when the customer runs the script. Actual submission behavior, quotas and duplicate handling still need a real disposable Google Form test.

## 15. Notifications

Staff verification, processing start, needs-attention events, READY release and payment rejection create real owner-scoped in-app notifications. The bell polls the real unread count. The notification page has pagination, order links, mark-read and mark-all-read. No push/SMS/WhatsApp notification infrastructure was added.

## 16. Admin/operator workflow

Django Admin lists/searches orders and filters service/status/payment. Its audited actions verify payment, start processing, release ready results, or complete delivery. Rejection links to the order workspace where a reason is mandatory. Order events and raw operational models are inspect-only in Admin so raw edits cannot bypass provenance/release checks.

The website staff workspace displays payment claim details, originals, paginated respondents, schema JSON, bank actions, processing/retry controls, missing/failed pages, manual page inspection, page correction, typed answer editing, confirmation, internal BotRun association, synthetic row edits, Google mappings, readiness failures and notes/audit history. Respondent sequence lookup reaches the whole batch. Correcting a confirmed response revokes its previous eligibility. Raw schema editing is an operator tool, not a claim of automatic schema extraction.

## 17. Render configuration

See [RENDER_TEST_DEPLOYMENT.md](RENDER_TEST_DEPLOYMENT.md) and `render.yaml`. The blueprint uses a Node frontend and API-only non-root Docker image, environment-driven URLs, database health check, migrations/static collection, private S3 storage, and manual mode. API uses Starter in the example to support standard SMTP; frontend can use free instances for tests. An optional properly sized paid worker/Redis deployment is documented for real OCR. Critical uploads cannot depend on ephemeral storage. No Render account was accessed or deployment performed.

## 18. Required environment variables

The deployment guide lists exact values and scope. Required groups are Django secret/hosts/CORS/CSRF/proxy settings; PostgreSQL URL; frontend API URL; bank details; positive digitization/synthetic NGN rates; processing mode; private bucket credentials; and working email sender/SMTP. Real OCR adds Redis and worker resources. Defaults disable Paystack and legacy customer tools. No secret is placed in NEXT_PUBLIC variables. Bank details and actual business prices remain deliberately unconfigured in the example; they must come from the business.

## 19. Tests added

Focused tests cover ownership and foreign attachments, immutable manual corrections, confirmation invalidation, spreadsheet injection, incomplete final exports, account suspension/reset/logout, order references/pricing/transitions, payment claims/verification/rejection/audit, complete versus missing/duplicate/corrupt uploads, changed-file idempotency, paid versus unpaid OCR dispatch, actual 480-page model representation and respondent pagination, operator review/ready revocation, synthetic template separation/content/labels/exports, blocked synthetic scripts, and notification ownership. The existing suites remain intact with updated final-data fixtures.

The browser test uses real local APIs and a disposable database: registration/login → order → valid image upload → bank claim → staff login/verification → manual inspection/page correction/answer approval → final script preparation/release → customer script and XLSX → notifications/logout. No API response mocks, fake OCR, money transfer, or Google execution are used. A separate printed-text OCR smoke check exercises real local engines.

## 20. Validation results

Validation was run against disposable databases and temporary browser-test uploads. No existing customer database was reset. Results:

| Validation | Result |
| --- | --- |
| Full backend suite, SQLite | **79 passed**, no skipped tests (27.75 s final run) |
| Full backend suite, PostgreSQL 16 | **79 passed**, no skipped tests (74.04 s final run) |
| Django system check | Passed, no issues |
| Migration consistency (`makemigrations --check --dry-run`) | Passed, no changes detected |
| Django deployment check with production security settings | Passed, no issues |
| Ruff | Passed |
| Frontend ESLint | Passed |
| TypeScript (`tsc --noEmit`) | Passed |
| Next.js production build | Passed; Next.js 15.5.24 |
| Playwright browser workflow | **1 passed** (1.3 min including startup; 48 s test) using installed Chrome, real APIs and explicit manual transcription |
| npm audit | 0 reported vulnerabilities after PostCSS override; applies to npm dependencies, not a blanket Python/OS security certification |
| Real Tesseract smoke | Passed: one printed page, recognized “Department: Engineering” |
| Real PaddleOCR smoke | Passed: one printed page, recognized the same text using cached models |
| Docker Compose configuration | Valid |
| Render API Docker build | Passed; API-only image with no embedded project SQLite database |
| Container migrations/static collection/deployment check | Passed on a fresh disposable database; 163 static files copied |
| Container Gunicorn startup and HTTP health | Passed; `/health/` returned 200/ok, process ran as UID 10001; temporary containers removed |
| Actual Render deployment | **Not performed** |
| Actual Google Form submission | **Not performed** |
| Live bank/SMTP/private bucket acceptance | **Not performed** |

The first PostgreSQL run exposed a nullable-join lock bug; it was fixed and the complete suite rerun. Browser tests exposed corrupt-image handling, a nested staff-authorization mismatch, a review-status mismatch and editing during an in-flight page refresh; all were fixed before the passing run. The bundled browser download timed out, so the suite ran with the installed Chrome binary instead. Local Node 20.18.1 emitted an engine advisory for an ESLint dependency; Render is configured for Node 22. These results establish local behavior, not external-service or production readiness.

## 21. Remaining limitations

- Render, real SMTP, private object-store credentials, actual bank statement verification, and real Google Form execution have not been validated against the customer's accounts.
- OCR smoke tests cover printed text, not measured handwriting/checkbox/Likert accuracy. Large-batch OCR throughput, memory, worker crashes/timeouts and recovery need representative testing on the intended worker.
- Schema preparation, uncertain grouping and low-confidence answers require an operator. A single PDF must represent one complete respondent; splitting/moving individual PDF pages across respondents remains unsupported.
- Synthetic generator realism and complex grids require human inspection/correction. Classification prevents public synthetic Google submission; labelled CSV is the supported result.
- Resumable upload keys support safe retries, but there is no background mobile sync. Review is per respondent. Failed/stalled worker recovery may require an operator checking the worker and retrying; there is no distributed watchdog/outbox or production queue SLA.
- Correcting already-downloaded data revokes future application delivery but cannot recall customer copies or undo responses already submitted to Google.
- JWTs are stored in browser localStorage; protect the frontend against XSS. Logout revokes refresh tokens and clears the browser session; an already copied access token may remain valid for its short lifetime.
- No automated refund, cancellation/payment dispute process, retention policy enforcement, operational monitoring, or tested disaster-recovery process is claimed.

## 22. What remains manual

Configure real prices/bank details; compare payment claims against bank statements; prepare/check schemas; inspect page groupings and handwritten/ambiguous answers; transcribe in manual mode; approve respondents; inspect/correct synthetic data; verify Google title mapping; release READY; customer authorizes/runs Apps Script in Google; operator handles failures, customer support, backups and refunds outside the app.

## Readiness table

READY below means implemented and validated locally for the stated scope, **not production certification**.

| Capability | Status | Notes |
| --- | --- | --- |
| Landing page | READY | Two services, responsive navigation, no accuracy claims |
| Authentication | READY locally | Real SMTP and account recovery still need deployed acceptance |
| Digitization order | READY | Server pricing, ownership, counts and state transitions |
| 480-page batch model | READY | 480 page records / 120 respondents and full pagination tested; no throughput claim |
| OCR | BETA | Real local PaddleOCR and Tesseract printed-text smoke checks; representative documents still need testing |
| Page grouping | BETA | Ordered images/explicit slots/full-respondent PDFs; uncertainty requires operator correction |
| Manual review | READY | Staff review, preserved human values, confirmation/release invalidation |
| Payment calculation | READY | Configurable NGN rates, immutable order price snapshot |
| Bank-transfer verification | READY, manual | Staff checks bank statement; no automatic bank verification |
| Final response generation | READY | Complete and explicitly reviewed respondents only |
| Apps Script generation | READY locally | Existing-form script, full title mapping, paid/released delivery |
| Apps Script instructions | READY | Copy/download and all requested execution steps |
| Synthetic order | READY | One blank template, separate requested synthetic count |
| Admin synthetic fulfillment | BETA | Existing generator plus manual edits; labelled CSV; synthetic Google submission blocked |
| Notifications | READY | Owner-scoped events, real unread count, read actions and order links |
| CSV/XLSX | READY | Final human rows; formula-safe output; synthetic labelled CSV only |
| Render deployment | INFRASTRUCTURE REQUIRED | Blueprint/API image/runbook prepared; no live deployment performed |
| Google real-form validation | TESTING REQUIRED | No external Google execution or ownership verification claimed |

## Answers to the twelve readiness questions

1. **Can a customer sign up and create a digitization order?** Yes, with configured rates and working email delivery. The real local browser path passes.
2. **Can they upload multiple respondents?** Yes: ordered images, explicit phone/page slots, or a complete PDF per respondent. Not arbitrary shuffled respondents or a combined multi-respondent PDF.
3. **Is payment required before OCR?** Yes. Upload creates no OCR job; both operator processing and the worker enforce verified payment for an order.
4. **Can only an admin verify payment?** Yes: an active staff operator is required; the customer's claim never verifies itself.
5. **Can a paid digitization order generate Apps Script?** Yes, after all respondents are valid/confirmed and every question is mapped. Staff prepares it, then releases READY.
6. **Can a synthetic customer submit a paid request?** Yes, through the synthetic order and the same bank-verification workflow.
7. **Can an admin fulfill it manually?** Yes, using verified schema preparation, internal generation/result association and row corrections. Complex/failed runs may need technical operator help.
8. **Can the customer retrieve the result?** Yes, when paid and released. Human data supports script/CSV/XLSX; synthetic data supports explicitly labelled CSV.
9. **Can User A access User B's data?** Normal customers are denied, including by known IDs/references. Explicit authorized staff access is intentional and tested.
10. **Can this build be exposed for controlled Render beta?** It is a candidate after configuration and the documented live acceptance checks. It has not been deployed or validated on Render here, so deployment safety is not asserted from tests alone.
11. **What prevents production launch?** Unvalidated external deployment/storage/email/Google behavior, unmeasured representative OCR accuracy and batch capacity, and untested backup/restore, monitoring and failure recovery. Operator capacity and payment reconciliation also need an actual service trial.
12. **What should be tested manually next?** Deploy the documented manual beta; verify real SMTP/reset, private persistent storage across redeploy, an actual bank claim/verification, two customers' isolation, a 2×4 digitization job including a corrected page, a five-page blank synthetic template, and Apps Script on a disposable existing Google Form. Then measure real OCR incrementally on representative scans with a proper worker.

## Git checkpoints

- `e5dc88e`: ownership, reviewed-answer integrity and spreadsheet safety.
- `4d04955`: orders, manual bank verification, paid processing and delivery gates.
- `9cc280b`: two-service frontend, operator workflows and additional regression fixes.
- Deployment/validation/report checkpoint follows these commits. No commits were pushed or deployed.

## Complete file inventory

- `.env.example`
- `.gitignore`
- `backend/.dockerignore`
- `backend/Dockerfile`
- `backend/Dockerfile.render`
- `backend/apps/accounts/serializers.py`
- `backend/apps/accounts/views.py`
- `backend/apps/billing/gateway.py`
- `backend/apps/billing/services.py`
- `backend/apps/billing/views.py`
- `backend/apps/botlab/admin.py`
- `backend/apps/botlab/migrations/0002_alter_syntheticresponse_data_label.py`
- `backend/apps/botlab/models.py`
- `backend/apps/botlab/views.py`
- `backend/apps/core/access.py`
- `backend/apps/core/admin.py`
- `backend/apps/core/spreadsheets.py`
- `backend/apps/core/throttles.py`
- `backend/apps/core/views.py`
- `backend/apps/documents/admin.py`
- `backend/apps/documents/migrations/0003_uploadeddocument_order_uploadeddocument_upload_key_and_more.py`
- `backend/apps/documents/models.py`
- `backend/apps/documents/serializers.py`
- `backend/apps/documents/services/grouping.py`
- `backend/apps/documents/tasks.py`
- `backend/apps/documents/validation.py`
- `backend/apps/documents/views.py`
- `backend/apps/exports/services.py`
- `backend/apps/exports/views.py`
- `backend/apps/googleforms/admin.py`
- `backend/apps/googleforms/serializers.py`
- `backend/apps/googleforms/services.py`
- `backend/apps/googleforms/views.py`
- `backend/apps/notifications/migrations/0002_alter_notification_kind.py`
- `backend/apps/notifications/models.py`
- `backend/apps/notifications/views.py`
- `backend/apps/orders/__init__.py`
- `backend/apps/orders/admin.py`
- `backend/apps/orders/apps.py`
- `backend/apps/orders/migrations/0001_initial.py`
- `backend/apps/orders/migrations/__init__.py`
- `backend/apps/orders/models.py`
- `backend/apps/orders/serializers.py`
- `backend/apps/orders/services.py`
- `backend/apps/orders/uploads.py`
- `backend/apps/orders/urls.py`
- `backend/apps/orders/views.py`
- `backend/apps/questionnaires/admin.py`
- `backend/apps/questionnaires/integrity.py`
- `backend/apps/questionnaires/migrations/0003_reviewed_answer_integrity.py`
- `backend/apps/questionnaires/models.py`
- `backend/apps/questionnaires/serializers.py`
- `backend/apps/questionnaires/views.py`
- `backend/config/settings.py`
- `backend/config/settings_test.py`
- `backend/config/urls.py`
- `backend/requirements/base.txt`
- `backend/scripts/e2e_server.py`
- `backend/scripts/start-web.sh`
- `backend/tests/test_auth.py`
- `backend/tests/test_botlab.py`
- `backend/tests/test_exports.py`
- `backend/tests/test_googleforms.py`
- `backend/tests/test_orders.py`
- `backend/tests/test_questionnaires.py`
- `backend/tests/test_response_grouping.py`
- `backend/tests/test_safety.py`
- `docs/MVP_IMPLEMENTATION_REPORT.md`
- `docs/RENDER_TEST_DEPLOYMENT.md`
- `frontend/app/(workspace)/account/page.tsx`
- `frontend/app/(workspace)/digitize/page.tsx`
- `frontend/app/(workspace)/layout.tsx`
- `frontend/app/(workspace)/notifications/page.tsx`
- `frontend/app/(workspace)/orders/[reference]/page.tsx`
- `frontend/app/(workspace)/orders/page.tsx`
- `frontend/app/(workspace)/synthetic/page.tsx`
- `frontend/app/dashboard/layout.tsx`
- `frontend/app/dashboard/page.tsx`
- `frontend/app/dashboard/review/[id]/page.tsx`
- `frontend/app/dashboard/settings/page.tsx`
- `frontend/app/forgot-password/page.tsx`
- `frontend/app/globals.css`
- `frontend/app/login/page.tsx`
- `frontend/app/page.tsx`
- `frontend/app/register/page.tsx`
- `frontend/app/reset-password/page.tsx`
- `frontend/components/OperatorOrder.tsx`
- `frontend/components/OrderForm.tsx`
- `frontend/components/OrderUploads.tsx`
- `frontend/components/PasswordRecovery.tsx`
- `frontend/components/ScriptInstructions.tsx`
- `frontend/components/Workspace.tsx`
- `frontend/e2e/orders.spec.ts`
- `frontend/lib/api.ts`
- `frontend/lib/orders.ts`
- `frontend/lib/types.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `render.yaml`
