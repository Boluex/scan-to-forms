# Private storage and remote OCR worker implementation report

2026-09-26. Baseline: `2b4ad8a`. Scope: private shared storage and external Celery OCR support only. **The Render → R2 → Ubuntu → Render PostgreSQL acceptance path remains REQUIRES OWNER ACTION.** No cloud resources were provisioned, no live credentials were available, and no customer data was migrated.

## Implementation

1. **Storage abstraction:** `open_source_file`, `source_response` and `materialize_source_file` centralize storage reads, authenticated streaming and bounded-memory temporary copies. Temporary directories/files are private; cleanup covers success, download failure and OCR exceptions. Filesystem development remains supported.
2. **Path audit:** no production `document.file.path` or `storage.path(...)` call was found. The existing task already copied `FieldFile.open()` into an inline temporary file. `MEDIA_ROOT` references were configuration/test-harness assumptions, not OCR path access. Existing previews opened fields through storage.
3. **Changes from that audit:** extracted the reusable helper, tightened permissions and bounded streaming, moved both preview endpoints onto it, and exercised a storage backend that rejects `path()` and `url()`. No claim is made that nonexistent path calls were fixed.
4. **R2 configuration:** `OBJECT_STORAGE_ENABLED` selects the existing django-storages S3 backend; the old `USE_S3_STORAGE` alias remains. Endpoint, bucket, credentials, region and addressing style are environment-driven. S3v4 signing, no ACL mutation, private cache policy and 1 MiB spool threshold are configured. No AWS account-specific operation is required.
5. **Private media:** existing owner/staff authorization remains before streaming. Responses are private/no-store. No public object URL or signed URL is added. New keys contain owner/order/document UUIDs and a random basename with a whitelisted extension; original filenames remain separate metadata. Bucket privacy still requires the owner's cloud configuration.
6. **Cleanup:** document deletion, including queryset/cascade deletion, records a durable cleanup intent in the same transaction. Physical deletion occurs after commit; rollback preserves the source. Storage errors retain the intent for `cleanup_source_files`. Existing order deletion protections remain. Cleanup fails closed on storage identity changes or still-referenced keys.
7. **Remote worker configuration:** `.env.worker.example`, selectable `SCANTO_FORMS_ENV_FILE`, and a runbook for the existing Docker/native worker. API and worker must use the same database, queue and private bucket. No worker is added to the free Render blueprint.
8. **Redis/TLS:** `rediss://` enforces certificate and hostname verification in broker and result-backend parameters. Insecure overrides are rejected. Optional CA path is supported. Local Compose `redis://` behavior remains unchanged. No actual external TLS handshake was performed.
9. **OCR behavior:** source streams to a temporary local file for the unchanged PaddleOCR/Tesseract/OpenCV pipeline. Real local JPG, PNG and image-only PDF smoke tests passed with each engine. Real Tesseract tasks also saved database results through the pathless test backend. **Neither test used real R2.**
10. **Payment gate:** upload and PAYMENT_SUBMITTED remain unpaid. Existing processing and document retry, new recovery endpoint, and direct task execution reject unpaid order work. Only the existing staff-verification flow unlocks processing. Recovery itself requires staff authorization.
11. **Recovery:** staff can retry eligible queued/failed/abandoned digitization jobs from the order UI, Admin or `POST /api/v1/orders/{reference}/retry-processing/`. Jobs remain authoritative in PostgreSQL when broker messages disappear. Nonblocking session advisory locks exclude active executions; execution tokens reject superseded writes. Completed/review-ready jobs are skipped. Stale PROCESSING requires an expired threshold and no active lock. Recovery is audited and invalidates response confirmation while retaining human corrections.

## Exact files changed

Existing files:

- `.env.example`
- `.gitignore`
- `backend/config/settings.py`
- `backend/apps/documents/admin.py`
- `backend/apps/documents/apps.py`
- `backend/apps/documents/models.py`
- `backend/apps/documents/tasks.py`
- `backend/apps/documents/views.py`
- `backend/apps/documents/management/commands/ocr_smoke_test.py`
- `backend/apps/orders/admin.py`
- `backend/apps/orders/services.py`
- `backend/apps/orders/uploads.py`
- `backend/apps/orders/views.py`
- `frontend/components/OperatorOrder.tsx`
- `docs/RENDER_TEST_DEPLOYMENT.md`

New files:

- `.env.worker.example`
- `backend/config/connections.py`
- `backend/apps/documents/storage.py`
- `backend/apps/documents/cleanup.py`
- `backend/apps/documents/execution.py`
- `backend/apps/documents/management/commands/cleanup_source_files.py`
- `backend/apps/documents/migrations/0004_storagedeletion_ocrjob_execution_token.py`
- `backend/tests/test_storage.py`
- `backend/tests/test_worker_recovery.py`
- `docs/R2_STORAGE_SETUP.md`
- `docs/REMOTE_OCR_WORKER.md`
- `docs/OBJECT_STORAGE_REMOTE_WORKER_REPORT.md`

## Migration and dependencies

The single new migration adds `StorageDeletion` and nullable `OCRJob.execution_token`. It preserves existing data and file keys. Test databases applied it successfully; the owner must deploy it to Render before starting the new worker. No existing customer database was reset.

**No new dependencies.** The implementation reuses Django, django-storages/boto3, Celery/Redis, psycopg and the existing OCR dependencies. The Render blueprint, payment/pricing, customer services and warning text remain unchanged.

## Tests and validation

Thirty new parameterized test cases cover private upload/preview, scoped random keys and filename handling, owner/staff isolation, local/pathless materialization, bounded reads and cleanup after failure, cascade/rollback/deferred deletion, real image/PDF OCR result persistence, unpaid processing gates, staff recovery, duplicate/late execution protection and TLS parameters. PostgreSQL tests exercise advisory-lock contention through a second real database connection.

| Check | Result / boundary |
| --- | --- |
| Backend, SQLite | **120 passed**, including local filesystem and pathless-storage cases |
| Backend, PostgreSQL 16 | **120 passed in 53.45s**, isolated temporary PostgreSQL container; no skips |
| Django check | Passed, no issues |
| Migration consistency | Passed, no changes detected |
| Ruff | Passed |
| Frontend ESLint | Passed |
| TypeScript | Passed |
| Next.js production build | Passed, all 22 routes built |
| Docker Compose config | Passed validation; Compose architecture unchanged |
| API production Docker build | Passed, `scantoforms-api:storage-check` |
| OCR production Docker build | Passed, `scantoforms-ocr-worker:storage-check`, existing non-root concurrency-1 target |
| Built worker application check | Passed offline: Django setup, Celery OCR task registration, PaddleOCR/OpenCV imports; no broker connection claimed |
| Real Tesseract storage smoke | JPG, PNG, image-only PDF passed using local filesystem storage |
| Real PaddleOCR storage smoke | JPG, PNG, image-only PDF passed using local filesystem storage |
| Real Tesseract task with pathless storage | JPG, PNG, PDF passed; results persisted; temporary copies removed |
| R2/S3 service round-trip | **NOT RUN**: no connected bucket; pathless test storage is not an S3 protocol test |
| Remote queue/TLS handshake | **NOT RUN**: owner connections required |
| Render/Ubuntu eight-page acceptance | **NOT RUN**: owner connections required |
| Render redeploy persistence | **NOT RUN**: no provisioned bucket/live deployment in this task |

An initial PostgreSQL run found a test-harness issue: closing a streaming response inside pytest's outer transaction closed its connection. That preview test now uses a real transactional test lifecycle; the full PostgreSQL suite was rerun successfully. This was not hidden as a passing initial run. A local MinIO acquisition attempt was unavailable, so no local S3 server acceptance is claimed. This task did not rerun the previous browser E2E; the only frontend change is the staff retry control, with its API covered by backend tests.

## Owner actions

**Cloudflare:** review billing/allowances, enable R2, create a private bucket, disable public endpoints, create bucket-scoped credentials, obtain the S3 endpoint. Follow [R2_STORAGE_SETUP.md](R2_STORAGE_SETUP.md). No secrets belong in chat or Git.

**Render:** deploy the migration/code, enter object-storage secrets directly, retain the API's existing bank/pricing/auth configuration, allow only the worker's public IP for external DB/Key Value connections. The API can keep internal URLs; the worker needs external ones. Keep both customer notices until actual tests justify each change. Existing local files are not migrated by toggling a flag.

**Ubuntu:** use matching code, fill the ignored `.env.worker`, use direct external PostgreSQL with hostname/certificate verification and authenticated `rediss://`, configure the same private bucket, start the existing concurrency-1 worker, verify registration and perform real paid-order acceptance. Follow [REMOTE_OCR_WORKER.md](REMOTE_OCR_WORKER.md).

## Remaining limitations

- No R2, Render or external-worker end-to-end execution/persistence result exists yet. Unit tests and local OCR are distinct evidence.
- Direct PostgreSQL sessions are required for execution locks; transaction-pooled PgBouncer is unsupported for this worker topology. SQLite locking is only a single-worker-process fallback.
- Worker downtime leaves work pending; recovery is operator-controlled. There is no 24/7 availability promise or periodic automated recovery service.
- Existing Render free-resource expiration/quotas still apply. Object storage does not make an expiring free database durable. Free object-storage allowances do not guarantee a spending cap.
- Normal exception cleanup is tested. SIGKILL/machine failure can leave temporary files; protect the worker disk and remove confirmed stale copies. Source upload plus database commit is not distributed-atomic, so a crash between them may leave an orphan object.
- Large PDF rendering/OCR still consumes memory. These printed-fixture tests do not establish handwriting, checkbox/Likert accuracy, arbitrary page grouping or 480-page capacity.
- Existing local source objects need explicit migration or permitted re-upload before switching a populated deployment. Pending cleanup records must be retried against their original storage configuration.
- Real Google Form submission remains a separate owner-authorized test. No OAuth or synthetic Google submission was enabled.

## Capability status

| Capability | Status |
| --- | --- |
| Local filesystem | PASSED LOCALLY |
| R2 object storage | CONFIGURED IN CODE; REQUIRES OWNER ACTION |
| Private uploads | LOCAL AUTHORIZATION TESTS PASSED; live bucket privacy unverified |
| Remote API access | Existing API retained; live acceptance requires owner action |
| Remote Celery queue | TLS configuration tested; live connection unverified |
| Remote worker | Setup prepared; not connected to Render |
| PaddleOCR via R2 | REQUIRES OWNER ACTION; local real-engine storage smoke passed |
| Tesseract via R2 | REQUIRES OWNER ACTION; local/pathless real-engine tests passed |
| PDF OCR via R2 | REQUIRES OWNER ACTION; local image-only PDF tests passed |
| Payment-gated OCR | SQLite/PostgreSQL regression tests passed |
| Worker-offline recovery | Database/locking regression tests passed; remote exercise pending |
| Render persistence | REQUIRES OWNER ACTION; not validated |
| Cross-user isolation | Local SQLite/PostgreSQL tests passed; live acceptance pending |
