# Ubuntu OCR worker for the Render beta

Status: **prepared and tested locally; Render → R2 → Ubuntu acceptance REQUIRES OWNER ACTION**. This is the existing Celery worker running on your computer, not a Render Background Worker. No paid Render service or inline API worker is introduced. Availability depends on the computer, its network and your operating schedule; there is no 24/7 processing promise.

## Prerequisites and connection checklist

Use the same repository revision as the API. Complete [private R2 setup](R2_STORAGE_SETUP.md), configure the API to use it, and apply `documents.0004_storagedeletion_ocrjob_execution_token` through the normal API migration startup before starting the worker. No database reset is needed.

| Variable | Ubuntu setting |
| --- | --- |
| `DJANGO_SECRET_KEY` | Existing API Django secret, supplied privately |
| `DJANGO_DEBUG` | `false` |
| `DATABASE_URL` | Render **external direct PostgreSQL** URL, with certificate/hostname verification |
| `REDIS_URL` | Same Render Key Value instance/database as the API, using its **external `rediss://`** authenticated URL |
| `REDIS_SSL_CA_CERTS` | Optional absolute path to a trusted CA PEM if system roots are insufficient; blank normally |
| `OBJECT_STORAGE_ENABLED` | `true` |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Bucket-scoped credentials |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL` | Same private bucket and HTTPS endpoint as API |
| `AWS_S3_REGION_NAME`, `AWS_S3_ADDRESSING_STYLE` | `auto`, `path` for R2 |
| `PROCESSING_MODE`, `CELERY_TASK_ALWAYS_EAGER` | `celery`, `false` |
| `OCR_ENGINE` | `auto` (PaddleOCR primary, Tesseract fallback) |
| `PADDLEOCR_DEVICE`, `PADDLEOCR_LANG` | `cpu`, `en` for initial English printed-text test |
| `OCR_STALE_AFTER_SECONDS` | `900`; code enforces at least 660, above the 600-second task hard limit |
| `ENABLE_LEGACY_WORKSPACE`, `ENABLE_PAYSTACK`, `TEST_DEPLOYMENT` | `false`, `false`, `true` |

Keep API bank/pricing/email/frontend settings in Render. They are not needed to process existing OCR jobs. Keep the API in Celery mode with eager execution disabled. Its existing internal database/queue connections may remain; Ubuntu must use the corresponding external connections, never unreachable Render internal hostnames.

In Render, enable external database and Key Value access only for your current public IP (`/32` for a single IPv4 address). Update it if your ISP changes the address; do not use `0.0.0.0/0` as a workaround. External Key Value access is disabled until allowed and requires authenticated TLS. See [Render Key Value connections](https://render.com/docs/key-value).

For PostgreSQL, preserve the provider hostname and use `sslmode=verify-full` with an appropriate trusted root. On Ubuntu the system CA path is usually `/etc/ssl/certs/ca-certificates.crt`; add `sslrootcert` to the URL's query if needed. Add query parameters with `?` or `&` as appropriate and keep the URL private. Do not replace the host with a cached IP or disable verification after a certificate error. See [Render PostgreSQL connections](https://render.com/docs/postgresql-creating-connecting).

**Use a direct database connection, not transaction-pooled PgBouncer.** OCR/recovery exclusivity uses PostgreSQL session advisory locks. A transaction pool may switch the physical connection between transactions and cannot provide that guarantee. See [Render pooling behavior](https://render.com/docs/postgresql-connection-pooling).

For `rediss://`, application configuration enforces certificate and hostname verification for both the broker and result backend; weak URL overrides are rejected. A custom CA path must exist inside the container if using Docker. Never set `ssl_cert_reqs=none` or disable verification globally. See [Celery TLS configuration](https://docs.celeryq.dev/en/stable/userguide/configuration.html#broker-use-ssl).

## Recommended: existing Docker worker target

Install Docker Engine using its supported Ubuntu installation procedure. From the repository root:

```bash
cp .env.worker.example .env.worker
chmod 600 .env.worker
# Edit .env.worker privately; fill all blank required values.
docker build --target ocr-production -t scantoforms-ocr-worker -f backend/Dockerfile backend
docker volume create scantoforms-ocr-models
docker run -d --name scantoforms-ocr-worker --stop-timeout 660 \
  --env-file .env.worker \
  -e PADDLE_PDX_CACHE_HOME=/home/appuser/.paddlex \
  -v scantoforms-ocr-models:/home/appuser/.paddlex \
  scantoforms-ocr-worker
```

The image runs non-root with concurrency 1, PaddleOCR/Tesseract/OpenCV dependencies and the existing prefork worker. The named volume holds downloaded OCR models, not questionnaire originals. Initial model downloads need network access and disk; first OCR is slower. Do not mount a host `.env` inside the image, expose worker ports, or install an unrelated queue/DB locally for this remote deployment.

Inspect registration and normal logs:

```bash
docker exec scantoforms-ocr-worker celery -A config inspect ping
docker exec scantoforms-ocr-worker celery -A config inspect registered
docker logs --tail 100 -f scantoforms-ocr-worker
```

Expect a worker reply and registration of `apps.documents.tasks.process_document`. A reply proves connectivity, not successful OCR. Keep logs private; do not dump settings or run commands that print credentials.

Optional real-engine storage smoke checks, using generated disposable printed fixtures (JPG, PNG and image-only PDF):

```bash
docker exec scantoforms-ocr-worker python manage.py ocr_smoke_test --storage --engine paddleocr
docker exec scantoforms-ocr-worker python manage.py ocr_smoke_test --storage --engine tesseract
```

These write/read/delete unique diagnostic objects through the configured storage. They run real engines but do not create customer orders, prove queue execution or bypass customer payment. Resolve a diagnostic cleanup failure explicitly. Run the actual acceptance job below as well.

Stop safely with a warm shutdown:

```bash
docker stop --time 660 scantoforms-ocr-worker
```

Allow the current bounded task to finish; avoid forcibly killing the container. After a code update, build the new image, stop/remove the old container, then repeat the run command. Keep the model volume. Do not start old and new revisions against incompatible migrations.

## Native Python alternative

Use Python 3.13, matching the project image, plus the existing system OCR packages. For an Ubuntu installation with Python 3.13 available:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr libmagic1 libgl1 libglib2.0-0 fonts-dejavu-core ca-certificates
python3.13 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements/base.txt -r backend/requirements/ocr.txt
# Start from repository root after privately configuring .env.worker.
export SCANTO_FORMS_ENV_FILE="$PWD/.env.worker"
cd backend
.venv/bin/celery -A config worker -l info --concurrency 1 --hostname 'ubuntu@%h'
```

If the Ubuntu release lacks this Python version/venv support, use the Docker option instead of changing the application's Python dependency versions. In a second shell, select the same `SCANTO_FORMS_ENV_FILE`, then run `.venv/bin/celery -A config inspect ping` or `inspect registered` from `backend`. Ctrl-C once requests warm shutdown. Do not use eager execution or a thread/solo pool as a substitute for the bounded prefork worker.

## Offline behavior and operator recovery

PostgreSQL retains orders, payment state, documents and OCR jobs when the worker is offline. Redis is only transport/result cache; free Key Value loss can remove messages. A queued order is not evidence that its message still exists.

After reconnecting the worker, staff can use **RETRY PROCESSING** in the order operator panel or Django Admin; the equivalent authenticated staff API is `POST /api/v1/orders/{reference}/retry-processing/`. It requires verified payment and a digitization order in Celery mode. Eligible queued/failed jobs are republished. A PROCESSING job must be older than the stale threshold and have no active execution lock. Completed or review-ready jobs are skipped. No eligible work returns a validation error. Recovery is audited.

An execution token fences late writes; PostgreSQL locks exclude concurrent processing of the same job, including duplicate queue messages. SQLite is only a single-worker-process development fallback. A PROCESSING job without a start timestamp is not automatically reset: investigate it instead of guessing that execution stopped. Recovering a response invalidates confirmation and preserves human answer precedence. Review again before delivery.

Recovery does not revive expired databases or missing objects. Free Render database lifetime/quotas remain constraints; record the expiration date and arrange an approved durable database before keeping customer data. If source deletion was deferred during a storage outage, run `python manage.py cleanup_source_files --limit 100` with the same database/storage configuration.

## Required live acceptance record

Keep warnings and acceptance status unchanged until evidence exists. With owner-authorized Render, R2 and Ubuntu connections:

1. Create customers A/B and a disposable printed questionnaire. Customer A creates a 2-respondent × 4-page digitization order and uploads 8 ordered source pages. Confirm private bucket keys and upload counts.
2. Confirm upload/payment claim do not run OCR. PAYMENT_SUBMITTED is still unpaid; customer verification/process/retry attempts must fail. Staff records verification, prepares/verifies schema and starts processing.
3. Record job IDs, queue receipt, real engine used, approximate duration, worker memory where observable, failures/retries and database results. Confirm the worker's temporary copy disappears after success/failure.
4. Check exactly 2 logical respondents, each with 4 pages. Review uncertain grouping/answers, correct an answer, reaggregate and confirm the correction survives. Confirm only final reviewed responses reach delivery.
5. Test A/B source/order/page/export isolation and authorized staff access. Check CSV/XLSX/Apps Script delivery through the existing paid-ready flow; synthetic Google submission stays blocked.
6. Download source bytes, redeploy the API and restart the worker, then verify source hashes, permitted previews, database records and generated results. Do not infer persistence solely from database rows.
7. With no active task, simulate a lost message using a dedicated disposable test queue/environment or the existing failure test procedure; never flush a shared broker. Demonstrate staff recovery republishes eligible durable work and completed jobs are not rerun.
8. Record remaining limitations explicitly. Eight pages do not validate 480-page throughput. Real Google authorization/submission remains a separate owner-operated acceptance test.

This topology leaves the customer product flow unchanged. It requires verified private storage, functioning external network access and an available worker before promising OCR turnaround or accepting paid pilots.
