# ScanToForms controlled beta on Render

This is a two-customer-service, operator-assisted beta. It is **not** a 480-page OCR production deployment. No Render resources have been created from this workspace. The current blueprint is prepared for real queued OCR acceptance; it has not passed live acceptance. See [the live acceptance report](RENDER_LIVE_ACCEPTANCE_REPORT.md) for evidence and blockers.

## Deployment for the real-OCR acceptance test

`render.yaml` defines a Node 22 Next.js web service, a Django Docker API built from `backend/Dockerfile.render`, a separate Celery OCR worker, and private Render Key Value. Supply PostgreSQL, a **private** S3-compatible bucket, and SMTP. The API retains its existing paid `starter` plan. The worker's `2c-4g` plan is an initial measurement candidate, not proven sufficient capacity. The queue uses paid `256mb`, `noeviction`, and `journal-snapshot` persistence. The frontend can be free for controlled tests. Review the workspace's actual quoted cost and resource availability before creation. No resources have been purchased or deployed here.

Both API and worker use `PROCESSING_MODE=celery` and `CELERY_TASK_ALWAYS_EAGER=false`. The worker references the API's database and private storage configuration, and both reference the same queue. Run one worker at concurrency 1. The API startup applies migrations; confirm migration completion before submitting any work. Keep services and database in the same Render region. This blueprint does not provision PostgreSQL or an object-storage bucket.

Manual mode remains available in the application for real human transcription, but does **not** satisfy this acceptance test. Do not change to manual mode or eager tasks to report the queue/OCR path as passing. Synthetic fulfillment still uses the existing deterministic generator plus operator inspection; it does not call an LLM.

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

## Exact environment-variable checklist

These names match `backend/config/settings.py`. Bare `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` environment variables are **not** read by this app: use the `DJANGO_` names below. Configure secrets in Render, never in Git or `NEXT_PUBLIC_*`. Values in angle brackets are placeholders, not deployable values.

| Variable | Service | Required value / source |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | API → worker reference | Unique generated secret; keep stable across redeploys |
| `DJANGO_DEBUG` | API + worker | `false` |
| `DJANGO_ALLOWED_HOSTS` | API | `<actual-api-host>.onrender.com` (host only, comma-separated if needed; no wildcard) |
| `DJANGO_TRUST_PROXY` | API | `true` behind Render's managed proxy |
| `DJANGO_CORS_ALLOWED_ORIGINS` | API | `https://<actual-frontend-host>.onrender.com` (no trailing slash) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | API | Exact HTTPS API/admin and frontend origins, comma-separated |
| `FRONTEND_URL` | API | Exact HTTPS frontend origin for account emails |
| `DATABASE_URL` | API → worker reference | Same persistent PostgreSQL database URL; provider-required TLS parameters; never SQLite |
| `REDIS_URL` | API + worker | Blueprint reference to private `scantoforms-redis` connection string |
| `PROCESSING_MODE` | API + worker | `celery` |
| `CELERY_TASK_ALWAYS_EAGER` | API + worker | `false` |
| `TEST_DEPLOYMENT` | API + worker | `true`; labels the deployment, does not mock OCR |
| `ENABLE_LEGACY_WORKSPACE` | API + worker | `false` |
| `ENABLE_PAYSTACK` | API + worker | `false`; no Paystack keys needed |
| `MANUAL_BANK_TRANSFER_ENABLED` | API | `true` |
| `BANK_NAME` | API | Actual business bank name |
| `BANK_ACCOUNT_NAME` | API | Actual account holder |
| `BANK_ACCOUNT_NUMBER` | API | Actual bank account number; customer-visible payment instruction |
| `DIGITIZATION_PRICE_PER_RESPONDENT_NGN` | API | Business-approved positive decimal NGN rate |
| `SYNTHETIC_PRICE_PER_RESPONSE_NGN` | API | Business-approved positive decimal NGN rate |
| `USE_S3_STORAGE` | API + worker | `true` |
| `AWS_STORAGE_BUCKET_NAME` | API → worker reference | Same private bucket |
| `AWS_ACCESS_KEY_ID` | API → worker reference | Scoped storage access key |
| `AWS_SECRET_ACCESS_KEY` | API → worker reference | Scoped storage secret |
| `AWS_S3_REGION_NAME` | API → worker reference | Bucket provider's region |
| `AWS_S3_ENDPOINT_URL` | API → worker reference | HTTPS endpoint for S3-compatible providers; empty for standard AWS S3 |
| `EMAIL_BACKEND` | API | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | API | Real SMTP hostname |
| `EMAIL_PORT` | API | `587` for this STARTTLS configuration |
| `EMAIL_HOST_USER` | API | SMTP login |
| `EMAIL_HOST_PASSWORD` | API | SMTP secret |
| `EMAIL_USE_TLS` | API | `true` |
| `DEFAULT_FROM_EMAIL` | API | Verified sender accepted by the provider |
| `ADMIN_CONTACT_EMAIL` | API, optional | Monitored support address |
| `RENDER_TARGET` | Worker build | `ocr-production`; do not set this on the API |
| `OCR_ENGINE` | Worker | `auto` for PaddleOCR with real Tesseract fallback; record the engine actually used |
| `PADDLEOCR_DEVICE` | Worker | `cpu` |
| `PADDLE_PDX_CACHE_HOME` | Worker | `/home/appuser/.paddlex`; replaceable model cache, not customer storage |
| `NODE_VERSION` | Frontend | `22` |
| `NEXT_PUBLIC_API_URL` | Frontend build + runtime | `https://<actual-api-host>.onrender.com/api/v1`; rebuild after changes |

Optional limits: `MAX_ORDER_RESPONDENTS` (default 1000), `MAX_ORDER_PAGES` (5000), `MAX_SYNTHETIC_RESPONSES` (1000), `MAX_UPLOAD_BYTES` (26214400 per file), `MAX_PDF_PAGES` (100). Defaults are validation limits, **not tested processing capacity**. The first live job is 2 respondents × 4 pages. `WEB_CONCURRENCY` defaults to 1. Render supplies `PORT`; do not override it. `RUN_MIGRATIONS` defaults to `true` for the single API instance. Keep HTTPS redirect enabled (default when debug is off).

Worker references are synchronized by the Blueprint. After changing database/storage credentials, verify both services received the same configuration and restart them safely. Do not print connection strings or secrets into acceptance logs. Worker notifications are database records; SMTP runs in the API's account flow.

## Worker image, queue and storage checks

The main Dockerfile retains its existing named stages and now selects the final stage with a non-secret build argument, `RENDER_TARGET` (default `production`). Render translates service environment variables into Docker build arguments; the worker selects `ocr-production`. Its unchanged command is `celery -A config worker -l info --concurrency 1`. No undocumented Render `--target` setting is required. See [Render's Docker documentation](https://render.com/docs/docker).

After the API's migrations finish, verify the worker logs show a connected broker, registered `apps.documents.tasks.process_document` task, and a ready worker. Use an API shell to check `redis.Redis.from_url(settings.CELERY_BROKER_URL).ping()` and `config.celery.app.control.ping(timeout=10)`; a Redis PONG alone does not prove the worker is running. Confirm `/health/` separately: it only executes a database query. Verify `/admin/login/` and its static CSS, the frontend, and authenticated notifications.

API and worker cannot share a Render service disk. Their shared bucket is the source of truth: `UploadedDocument.file` uses Django's S3 storage; the worker downloads a source into a temporary local directory for OCR. That local copy is disposable. The application does not mount a public `/media/` route; source downloads use authenticated owner/staff endpoints. `default_acl=None` does **not** make a public bucket private: disable public bucket policies and verify an unsigned object request cannot return file bytes. API/worker credentials must access the same objects. No browser S3 credentials or public bucket URL is needed.

Verify a test object's SHA-256 from both API and worker storage reads; record only document IDs and hashes. After all tasks finish, restart/redeploy API and worker and repeat those checks plus customer file download and output retrieval. Records/results live in PostgreSQL; Apps Script is stored in the database and CSV/XLSX are generated from persisted records. Neither a passing health check nor an S3 setting alone proves persistence. No local filesystem fallback is acceptable for this deployment.

The worker cache is ephemeral and may download models again after redeploy. Observe cold startup and actual per-job engine, duration, attempts, errors and worker memory. A Tesseract fallback is real OCR but is not evidence that Paddle succeeded. Free Render infrastructure does not provide a paid OCR worker or durable shared uploads; do not combine hidden processes in a free web service. The configured worker's 300-second shutdown grace is shorter than the 600-second task limit: drain work before planned redeploys. Unexpected worker death can leave processing jobs requiring operator recovery; no restart/retry guarantee has been demonstrated.

## Acceptance before inviting customers

- Register, receive verification email, log in, log out, reset password through a real email, and verify the old password/session is rejected.
- Create two respondents × four pages. Upload ordered images and phone slots; inspect order completeness. Test rejection of duplicated files and missing pages.
- Attempt processing/results before payment: blocked. Click I HAVE PAID: still blocked. Independently confirm a test transfer, then verify it using a staff account. Test rejection and resubmission.
- Prepare the schema, start the paid order, and trace actual job IDs from API → Redis → worker → PostgreSQL OCR results. Inspect every page/grouping, correct answers, approve them, confirm both respondents, map every Google item, prepare the script, and release READY. No manual-mode substitute for this test.
- Download CSV/XLSX/.GS, copy the code, run previewMapping in a disposable **existing** real Google Form, then startSubmission/continueSubmission/submissionStatus. Verify row count, checkbox/grid/date values and Google item titles. ScanToForms cannot remotely confirm success and must not claim it did.
- Create a synthetic order from one multi-page blank template. Generate/adjust a paid dataset, inspect every column, release labelled CSV. Google submission is intentionally blocked.
- Verify notifications and cross-account isolation, including guessed order references and original files.
- Redeploy/restart the API and verify files and rows still exist. Test storage access denial without authentication and document your backup/restore procedure.

For the separate Google test, use 5–10 known disposable test responses collected on controlled test questionnaires. The eight-page grouping job contains only two respondents and cannot prove five-response submission. Do not pass Bot Lab output through a human-response order to bypass synthetic classification. Record the disposable Form's baseline response count, every mapped title/type, expected values, final count and script status. Run `continueSubmission()` again after completion in the same project and verify no duplicates. Do not restart from a copied new project to test resumability; its state is separate. Record unsupported types individually, including blocked file-upload questions. Text, multiple choice, checkbox and scale need actual execution; generator branches for grids, dates, time, duration and rating are not proof of compatibility.

The existing Playwright config starts local disposable services and uses manual mode. Running `npm run test:e2e` does **not** exercise Render. Live testing must target the actual deployment URLs and retain redacted evidence; do not run the local database setup or its seeded credentials against Render.

## Data and deployment limitations

Ephemeral filesystem uploads are acceptable only for disposable local/testing data. Do not accept critical customer uploads with `USE_S3_STORAGE=false` on a free Render web instance. Persistent storage and tested recovery are required before a paying customer depends on the service. The blueprint cannot validate bank ownership, SMTP deliverability, object-store permissions, or Google execution; all need live acceptance testing.

The app does not verify Google Form ownership. It accepts standard edit URLs/IDs, rejects forms.gle and published `/d/e/` links, and never requests a Google password. A human checks `previewMapping()` before submitting. Do not restart a completed script casually: separate scripts/projects may submit duplicates.

## Repeatable local validation

From the repository root, use `.venv/bin/pytest backend/tests -ra`. Set `TEST_DATABASE_URL` to an **isolated test PostgreSQL database** to run the same suite against PostgreSQL; pytest creates its own `test_...` database. Never aim tests at a customer database. Run Django check/migration checks with `--settings=config.settings_test` if no local services are running.

From `frontend`, run `npm ci`, `npm run lint`, `npm run typecheck`, and `npm run build`. Browser tests use a disposable SQLite database and temporary upload directory, a local API on 8107 and frontend on 3107: `npx playwright install chromium`, then `npm run test:e2e`. Alternatively set `PLAYWRIGHT_CHROME_PATH` to an installed Chrome binary. The test operator credentials exist only in this temporary database. These tests use explicit manual transcription, not simulated OCR. They do not submit to Google or move real money.
