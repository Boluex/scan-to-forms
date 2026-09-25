# ScanToForms controlled beta on Render

This is a two-service, operator-assisted beta. It is **not** a 480-page OCR production deployment. No Render resources have been created by this refactor. Validate the blueprint in your Render account before deployment.

## Smallest deployment

`render.yaml` defines a Node 22 Next.js web service and a Django Docker API built from `backend/Dockerfile.render` (no Paddle worker dependencies). Supply a PostgreSQL database, a **private** S3-compatible bucket, and SMTP credentials. The API defaults to a paid Starter instance because free services block standard SMTP ports and cannot provide persistent disks. The frontend can be free for controlled tests; expect cold starts. No queue or worker is needed with `PROCESSING_MODE=manual`.

Manual mode is real operator transcription: pages stay unprocessed until an operator records inspection; answers are entered and approved by a human. It does not return fake OCR, invented confidence scores, or simulated Google submissions. Internal synthetic generation uses the existing deterministic generator, followed by operator inspection.

Render references: [Blueprint schema](https://render.com/docs/blueprint-spec), [free-tier restrictions](https://render.com/docs/free), [persistent disks](https://render.com/docs/disks), [background workers](https://render.com/docs/background-workers). Review current provider limits before choosing plans.

## Setup

1. Create PostgreSQL with a suitable lifetime and backups. Supply its connection URL as `DATABASE_URL`; use TLS as required by the provider. Do not use the local SQLite fallback remotely. Free Render PostgreSQL expires after 30 days and is only suitable for disposable tests.
2. Create a private S3-compatible bucket. Keep public access disabled; give the service credentials only the required bucket read/write/delete permissions. Supply bucket, access key, secret key, region, and optional endpoint URL. API downloads remain authenticated and owner scoped. Do not expose `/media/` through a public proxy.
3. Create the blueprint. Enter the API hostname in `DJANGO_ALLOWED_HOSTS` without a scheme. Set `FRONTEND_URL` and `DJANGO_CORS_ALLOWED_ORIGINS` to the exact HTTPS frontend origin. `DJANGO_CSRF_TRUSTED_ORIGINS` should include the HTTPS API origin for Django Admin and any approved browser origin. Keep `DJANGO_TRUST_PROXY=true` behind Render's managed proxy only.
4. Set frontend `NEXT_PUBLIC_API_URL=https://YOUR-API.onrender.com/api/v1` **before building**. Rebuild after changing it. This is a public URL, never a secret.
5. Set the bank account name, number, and bank name. Set positive NGN per-respondent/per-response prices. Pricing is calculated on the server and snapshotted on the order; later rate changes do not change existing orders.
6. Configure SMTP, TLS, and a verified sender. Send actual registration and reset emails to a test address. The console backend is for local tests only. If testing an entirely free API, standard SMTP will not work; do not invite real customers until account recovery delivery works on a supported service plan.
7. The API start script runs migrations once per instance and collects static assets. Keep one API instance initially. For multiple instances use a single pre-deploy migration step and `RUN_MIGRATIONS=false`. Never reset the database.
8. Run `python manage.py createsuperuser` in a secure Render shell. No default admin credentials are shipped. Log into Django Admin and `/orders` with this operator account.
9. Check `/health/`, then complete the acceptance steps below. It checks database connectivity, not worker/storage/email readiness.

## Environment variables

Required API: `DJANGO_SECRET_KEY` (generated), `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `FRONTEND_URL`, `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_TRUST_PROXY=true`.

Business: `MANUAL_BANK_TRANSFER_ENABLED=true`, `BANK_NAME`, `BANK_ACCOUNT_NAME`, `BANK_ACCOUNT_NUMBER`, `DIGITIZATION_PRICE_PER_RESPONDENT_NGN`, `SYNTHETIC_PRICE_PER_RESPONSE_NGN`. Prices default to zero and fail closed until configured.

Scope: `ENABLE_LEGACY_WORKSPACE=false`, `ENABLE_PAYSTACK=false`. Organizations, public Bot Lab, Google OAuth, and WhatsApp remain disabled. These flags do not implement those features.

Processing: `PROCESSING_MODE=manual`, `TEST_DEPLOYMENT=true`; configurable caps `MAX_ORDER_RESPONDENTS`, `MAX_ORDER_PAGES`, `MAX_SYNTHETIC_RESPONSES`. `MAX_UPLOAD_BYTES` defaults to 25 MB per file; `MAX_PDF_PAGES` defaults to 100.

Storage: `USE_S3_STORAGE=true`, `AWS_STORAGE_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_REGION_NAME`, optional `AWS_S3_ENDPOINT_URL`. Never put these in `NEXT_PUBLIC_*` variables.

Email: `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS=true`, `DEFAULT_FROM_EMAIL`. Optional `ADMIN_CONTACT_EMAIL`.

Frontend: `NODE_VERSION=22`, `NEXT_PUBLIC_API_URL`. Runtime `PORT` is supplied by Render; `WEB_CONCURRENCY` defaults to 1 for the API.

## Enabling real OCR later

Provision Redis/Render Key Value and a properly sized **paid worker**. Build `backend/Dockerfile` target `ocr-production` and run `celery -A config worker -l info --concurrency 1`. The Render blueprint uses the API-only Dockerfile. Select the worker target in the main Dockerfile explicitly in your build pipeline. Both services require the same database, private bucket, secret, pricing/feature flags, `PROCESSING_MODE=celery`, and `REDIS_URL`. Install the existing Paddle dependencies through the worker stage; allow model downloads/cache storage. Start with one small paid batch and measure memory, latency, failure recovery, and queue depth.

API and worker cannot share a Render service disk. Use the shared private bucket. Paddle model cache is separate and can use worker-local persistent storage if available. Do not run a hidden worker inside the free web service or claim provider capacity that has not been measured. Heavy OCR remains testable through local Docker Compose.

## Acceptance before inviting customers

- Register, receive verification email, log in, log out, reset password through a real email, and verify the old password/session is rejected.
- Create two respondents × four pages. Upload ordered images and phone slots; inspect order completeness. Test rejection of duplicated files and missing pages.
- Attempt processing/results before payment: blocked. Click I HAVE PAID: still blocked. Independently confirm a test transfer, then verify it using a staff account. Test rejection and resubmission.
- Prepare schema, inspect/transcribe pages, approve every answer, confirm every respondent, map every Google item, prepare script, and release READY.
- Download CSV/XLSX/.GS, copy the code, run previewMapping in a disposable **existing** real Google Form, then startSubmission/continueSubmission/submissionStatus. Verify row count, checkbox/grid/date values and Google item titles. ScanToForms cannot remotely confirm success and must not claim it did.
- Create a synthetic order from one multi-page blank template. Generate/adjust a paid dataset, inspect every column, release labelled CSV. Google submission is intentionally blocked.
- Verify notifications and cross-account isolation, including guessed order references and original files.
- Redeploy/restart the API and verify files and rows still exist. Test storage access denial without authentication and document your backup/restore procedure.

## Data and deployment limitations

Ephemeral filesystem uploads are acceptable only for disposable local/testing data. Do not accept critical customer uploads with `USE_S3_STORAGE=false` on a free Render web instance. Persistent storage and tested recovery are required before a paying customer depends on the service. The blueprint cannot validate bank ownership, SMTP deliverability, object-store permissions, or Google execution; all need live acceptance testing.

The app does not verify Google Form ownership. It accepts standard edit URLs/IDs, rejects forms.gle and published `/d/e/` links, and never requests a Google password. A human checks `previewMapping()` before submitting. Do not restart a completed script casually: separate scripts/projects may submit duplicates.

## Repeatable local validation

From the repository root, use `.venv/bin/pytest backend/tests -ra`. Set `TEST_DATABASE_URL` to an **isolated test PostgreSQL database** to run the same suite against PostgreSQL; pytest creates its own `test_...` database. Never aim tests at a customer database. Run Django check/migration checks with `--settings=config.settings_test` if no local services are running.

From `frontend`, run `npm ci`, `npm run lint`, `npm run typecheck`, and `npm run build`. Browser tests use a disposable SQLite database and temporary upload directory, a local API on 8107 and frontend on 3107: `npx playwright install chromium`, then `npm run test:e2e`. Alternatively set `PLAYWRIGHT_CHROME_PATH` to an installed Chrome binary. The test operator credentials exist only in this temporary database. These tests use explicit manual transcription, not simulated OCR. They do not submit to Google or move real money.
