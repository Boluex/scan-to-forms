# Ubuntu OCR worker for the external-services beta

Status: **ZERO-BUDGET / FREE-TIER CONTROLLED BETA; actual Neon / Upstash / R2 connectivity awaits credentials and live testing**. This is the existing Celery worker running on your Ubuntu computer. Render hosts only the API and frontend. Start the worker when paid/queued work exists, process the batch, then stop it. Availability depends on the computer and network; there is no 24/7 processing promise.

## Prerequisites and connection checklist

Use the same repository revision as the API. Complete [private R2 setup](R2_STORAGE_SETUP.md), configure the API to use it, and apply `documents.0004_storagedeletion_ocrjob_execution_token` through the normal API migration startup before starting the worker. No database reset is needed.

| Variable | Ubuntu setting |
| --- | --- |
| `DJANGO_SECRET_KEY` | Existing API Django secret, supplied privately |
| `DJANGO_DEBUG` | `false` |
| `EXTERNAL_SERVICES_REQUIRED` | `true`, same as the Render API |
| `DATABASE_URL` | Same **direct Neon PostgreSQL** URL as API; no `-pooler` hostname |
| `DATABASE_SSL_ROOT_CERT` | Optional trusted CA bundle path; blank uses the system CA bundle |
| `REDIS_URL` | Same **Upstash native authenticated `rediss://` URL**, database `/0`, as API |
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

Keep API bank/pricing/email/frontend settings in Render. They are not needed to process existing OCR jobs. Keep the API in Celery mode with eager execution disabled. Copy the same external provider URLs into the API and worker; there are no Render-internal database/queue connections in this architecture.

Complete [Neon setup](NEON_SETUP.md) and [Upstash setup](UPSTASH_REDIS_SETUP.md). Verify the endpoint/database names match privately on both sides. Do not print full connection URLs or put them in the frontend. Optional provider network controls depend on the plan; do not purchase an add-on for this beta.

For PostgreSQL, preserve the direct Neon hostname. Application settings upgrade `sslmode=require` to `verify-full` with a trusted system CA bundle; explicit TLS downgrades are rejected. On Ubuntu the CA path is usually `/etc/ssl/certs/ca-certificates.crt`. A custom path must also exist inside the container. Do not replace the hostname with an IP or disable verification after a certificate error.

**Use a direct database connection, not transaction-pooled PgBouncer.** OCR/recovery exclusivity uses PostgreSQL session advisory locks. A transaction pool may switch the physical connection between transactions and cannot provide that guarantee. See [Neon pooling behavior](https://neon.com/docs/connect/connection-pooling).

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

The image runs non-root with concurrency 1, PaddleOCR/Tesseract/OpenCV dependencies and the existing prefork worker. It has no automatic restart policy. Run it only when work is waiting. The named volume holds downloaded OCR models, not questionnaire originals. Initial model downloads need network access and disk; first OCR is slower. Do not mount a host `.env` inside the image, expose worker ports, or install an unrelated queue/DB locally for this deployment.

For lower coordination traffic, append `celery -A config worker -l info --concurrency=1 --without-gossip --without-mingle --without-heartbeat` after the image name in `docker run`. This still polls Redis. Do not run Flower, Beat or periodic inspect/keep-alive loops for this beta. Check Upstash usage before and after each batch.

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

Allow the current bounded task to finish; avoid forcibly killing the container. For the next queued batch, run `docker start scantoforms-ocr-worker`; it reuses the saved environment. If secrets/settings or code change, stop/remove only this worker container and recreate it with the updated environment/image. Keep the model volume. Do not start old and new revisions against incompatible migrations.

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

Neon PostgreSQL retains orders, payment state, documents and OCR jobs when the worker is offline. Upstash Redis is transport/result cache; lost messages, quota exhaustion or an outage must not erase business state. Celery results expire after one hour. A queued order is not evidence that its message still exists.

After reconnecting the worker, staff can use **RETRY PROCESSING** in the order operator panel or Django Admin; the equivalent authenticated staff API is `POST /api/v1/orders/{reference}/retry-processing/`. It requires verified payment and a digitization order in Celery mode. Eligible queued/failed jobs are republished. A PROCESSING job must be older than the stale threshold and have no active execution lock. Completed or review-ready jobs are skipped. No eligible work returns a validation error. Recovery is audited.

An execution token fences late writes; PostgreSQL locks exclude concurrent processing of the same job, including duplicate queue messages. SQLite is only a single-worker-process development fallback. A PROCESSING job without a start timestamp is not automatically reset: investigate it instead of guessing that execution stopped. Recovering a response invalidates confirmation and preserves human answer precedence. Review again before delivery.

Recovery does not recreate a deleted Neon database or missing R2 objects. Provider quotas and account access remain constraints. Pause work instead of upgrading if limits are reached. The existing recovery route covers digitization OCR, not synthetic-job recovery; no new workflow is added here. If source deletion was deferred during a storage outage, run `python manage.py cleanup_source_files --limit 100` with the same database/storage configuration.

## Required live acceptance record

Keep the controlled-beta notice and record actual acceptance evidence. With configured Render, Neon, Upstash, R2 and Ubuntu connections:

1. Create customers A/B and a disposable printed questionnaire. Customer A creates a 2-respondent × 4-page digitization order and uploads 8 ordered source pages. Confirm private bucket keys and upload counts.
2. Confirm upload/payment claim do not run OCR. PAYMENT_SUBMITTED is still unpaid; customer verification/process/retry attempts must fail. Staff records verification, prepares/verifies schema and starts processing.
3. Record job IDs, queue receipt, real engine used, approximate duration, worker memory where observable, failures/retries and database results. Confirm the worker's temporary copy disappears after success/failure.
4. Check exactly 2 logical respondents, each with 4 pages. Review uncertain grouping/answers, correct an answer, reaggregate and confirm the correction survives. Confirm only final reviewed responses reach delivery.
5. Test A/B source/order/page/export isolation and authorized staff access. Check CSV/XLSX/Apps Script delivery through the existing paid-ready flow; synthetic Google submission stays blocked.
6. Download source bytes, redeploy the API and restart the worker, then verify source hashes, permitted previews, database records and generated results. Do not infer persistence solely from database rows.
7. With no active task, simulate a lost message using a dedicated disposable test queue/environment or the existing failure test procedure; never flush a shared broker. Demonstrate staff recovery republishes eligible durable work and completed jobs are not rerun.
8. Record remaining limitations explicitly. Eight pages do not validate 480-page throughput. Real Google authorization/submission remains a separate owner-operated acceptance test.

This topology leaves the customer product flow unchanged. It requires verified private storage, functioning external network access and an available worker before promising OCR turnaround or accepting paid pilots.


## Ubuntu user services (this repository checkout)

`scripts/install-worker.py` installs two systemd **user** services using this checkout's `.venv`, ignored `.env.worker`, and persistent `.cache/paddlex`. Paths with spaces are supported. It sets one OCR process and one BLAS/OpenMP thread to begin conservatively. It does not install dependencies, enable automatic startup, or start push without credentials.

```bash
SCANTO_FORMS_ENV_FILE="$PWD/.env.worker" .venv/bin/python backend/manage.py worker_preflight
python3 scripts/install-worker.py --start
systemctl --user is-active scanforms-ocr
systemctl --user stop scanforms-ocr
systemctl --user start scanforms-ocr
journalctl --user -u scanforms-ocr -n 50 --no-pager
```

Preflight verifies database schema, broker connectivity and private bucket access without reading customer documents. Run it after code/config updates. Install matching requirements and apply migrations before restarting workers. The script keeps `.env.worker` permissions at `600`; it does not copy credentials into a service unit.

The worker can consume paid queued jobs once started. Stop it when no processing is needed for the controlled beta; Redis polling still incurs usage. Do not enable automatic login startup or user lingering unless you deliberately want continuous processing. User services depend on your user session, machine power and connectivity.

After configuring Firebase per [FIREBASE_SETUP.md](FIREBASE_SETUP.md), run `systemctl --user start scanforms-push`. This lightweight process drains the PostgreSQL notification outbox every 30 seconds independently of OCR. Leave it running if users need timely alerts; stopping OCR alone does not stop it. Without this sender, inbox records remain available but browser pushes wait. Firebase credentials belong in the API and sender; OCR-only hosts do not need them.
