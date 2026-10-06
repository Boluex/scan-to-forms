# Upstash Redis Free setup

Part of the **ZERO-BUDGET / FREE-TIER CONTROLLED BETA**. Use the existing Celery Redis transport over native TCP/TLS. Do not substitute the HTTP REST API or QStash. No real Upstash connection has been tested yet.

## Create and copy the connection

1. Sign in to the [Upstash console](https://console.upstash.com), create a Redis database, and explicitly choose **Free**. Prefer a region near the backend. Do not activate Pay As You Go or Fixed plans.
2. Leave **Eviction disabled**. If storage fills, failed queue publication is preferable to evicting existing jobs. Upstash's policy controls differ from Render's; there is no Render `maxmemoryPolicy` setting to configure. See [Upstash eviction](https://upstash.com/docs/redis/features/eviction).
3. In connection details, select the native Redis connection (Redis CLI/Python connection details). Copy the **host, port, username if provided, and database password/token**. Use the full native TLS URI if offered. An HTTPS REST URL and REST-specific environment variable names are not Celery configuration.
4. Set **exactly the same `REDIS_URL`** in Render backend secrets and Ubuntu `.env.worker`. Use database `/0`:

   ```text
   rediss://default:PASSWORD@HOST:PORT/0?ssl_cert_reqs=required&ssl_check_hostname=true
   ```

   The `:PASSWORD@` form is also supported when no username is provided. Copy provider credentials rather than inventing them. Percent-encode reserved characters if constructing a URI manually. Keep TLS switched on.
5. Set `EXTERNAL_SERVICES_REQUIRED=true` on both services. The application rejects plaintext Redis, REST URLs, missing authentication, disabled certificate verification and disabled hostname verification. `REDIS_SSL_CA_CERTS` is optional for a custom trusted CA file; normally leave it empty so system roots are used. Never use `ssl_cert_reqs=none`.

## Exact application configuration

`backend/config/settings.py` applies the same validated connection to broker and result backend:

```python
CELERY_BROKER_URL = secure_redis_url(
    os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    os.getenv("REDIS_SSL_CA_CERTS", ""),
    require_tls=EXTERNAL_SERVICES_REQUIRED,
)
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_RESULT_EXPIRES = 3600
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_TIME_LIMIT = 600
CELERY_TASK_SOFT_TIME_LIMIT = 540
```

`secure_redis_url` enforces `ssl_cert_reqs=required` and `ssl_check_hostname=true` on every `rediss://` connection. Local Docker development alone retains plaintext local Redis. Transport results expire after one hour; business/job state stays in PostgreSQL. Upstash documents support for Celery as both broker and result backend, but the actual account connection and real queue execution still require acceptance: [Upstash Celery integration](https://upstash.com/docs/redis/integrations/celery).

After filling the complete `.env.worker`, a one-off live connection check from the repository root is:

```bash
export SCANTO_FORMS_ENV_FILE="$PWD/.env.worker"
.venv/bin/python backend/manage.py shell -c 'from django.conf import settings; from redis import Redis; r = Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=10, socket_timeout=10); assert r.ping(); r.close(); print("Redis TLS ping passed")'
```

This consumes commands and proves connectivity only. Never repeatedly poll it as a keep-alive. The credentialless configuration tests do not run this command.

## On-demand worker and quota control

Current Free allowances checked September 28, 2026: **500,000 commands/month and 256 MB data**. Consult [Upstash pricing](https://upstash.com/pricing/redis) and the console for current limits. Do not add billing details that convert a database to a paid tier. A paid tier's first commands are not automatically free.

Celery polls Redis even without jobs. Connection checks, acknowledgements, result writes, event/worker coordination and retries also consume commands; there is no reliable commands-per-job estimate without measuring your run. Avoid Flower, frequent inspect calls, keep-alive loops and unattended workers.

Use this operating sequence:

1. Check paid/queued work in the application's PostgreSQL-backed operator view and check remaining Upstash quota.
2. Start the Ubuntu worker at concurrency 1 using [the worker guide](REMOTE_OCR_WORKER.md).
3. Process the batch; review actual database job/order state and observe provider command usage.
4. Once current work finishes, stop the worker with a warm shutdown. It is not intended to run 24/7.

Optional `--without-gossip --without-mingle --without-heartbeat` flags reduce coordination traffic; they do not eliminate polling or enforce a budget cap. No Celery Beat or automatic worker restart is required. If the quota is reached, stop processing and wait for allowance recovery instead of upgrading.

## Lost-message recovery

PostgreSQL remains authoritative. Never infer business completion from a Redis result or delete database state because a queue is empty. Preserve the existing staff **RETRY PROCESSING** action / `POST /api/v1/orders/{reference}/retry-processing/` for digitization orders. It republishes eligible queued/failed OCR jobs; stale processing jobs require no active PostgreSQL execution lock. Completed/review-ready jobs are skipped, payment gates remain enforced, and recovery is audited.

After a broker outage, quota exhaustion or missing task, restore connectivity/quota, start the worker, and use that action for eligible work. Do not flush a shared database or blindly reset statuses. The existing retry route is specific to digitization/OCR; this change does not add synthetic-job recovery or any new product feature. See the worker guide for exact recovery limits.
