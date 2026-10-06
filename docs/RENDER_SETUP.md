# ZERO-BUDGET / FREE-TIER CONTROLLED BETA

Render hosts only the Django API and Next.js frontend. Neon, Upstash, private Cloudflare R2 Standard storage and Resend are external. OCR runs on the owner's Ubuntu computer when work is waiting. No paid infrastructure is provisioned by this configuration, and no actual provider connectivity has been tested without credentials.

See [the local validation record](FREE_TIER_BETA_VALIDATION.md) for completed checks and the limits of that evidence.

```mermaid
flowchart TD
    Browser --> Frontend[Render Free Next.js Web Service]
    Frontend --> API[Render Free Django API]
    API --> Neon[Neon Free PostgreSQL]
    API --> Redis[Upstash Free Redis over TLS]
    API --> R2[Private Cloudflare R2 Standard bucket]
    API --> Email[Resend HTTPS API]
    Worker[Ubuntu Celery: PaddleOCR / Tesseract] --> Neon
    Worker --> Redis
    Worker --> R2
```

## Frontend hosting decision

Keep a **Render Free Web Service**. The existing application has dynamic `/orders/[reference]`, `/dashboard/questionnaires/[id]` and `/dashboard/review/[id]` pages. IDs/references are created after deployment, so they cannot be enumerated at build time. Client-side API fetching alone does not make those Next.js route files statically exportable.

An isolated trial with Next.js 15.5.24 and `output: "export"` compiled, then failed because `/orders/[reference]` lacks `generateStaticParams()`. No trial configuration was left in the app. Empty build-time params would not make new order URLs available on a static host. Keep the existing routing and `next start`; no major frontend rewrite is made. See [Next.js static-export limitations](https://nextjs.org/docs/app/guides/static-exports).

## Free-tier limits

Checked September 28, 2026; review provider consoles before use. These are allowances, not permanently free infrastructure or measured application capacity.

| Provider | Relevant allowance / constraint | Operating rule |
| --- | --- | --- |
| Render | 750 running web-service hours/month shared by the workspace; idle services sleep after 15 minutes; no persistent disk on Free | Two always-running services exceed the allowance; allow cold starts, monitor bandwidth/build usage, do not use keep-alives |
| Neon | 100 CU-hours/project, 0.5 GB database storage/project, 5 GB public network transfer/project; idle compute can suspend | Watch storage/compute/transfer and pause work before limits |
| Upstash Redis | 500,000 commands/month, 256 MB data | Run the worker on demand; polling consumes commands even with no jobs |
| R2 Standard | 10 GB-month storage, 1 million Class A and 10 million Class B operations/month; direct egress free | Overage can be billed without a plan upgrade; monitor usage and stop uploads/processing before exceeding allowances |
| Resend Free | 3,000 emails/month and 100/day | Keep test volume below both limits; use a verified sending domain for other recipients |
| Ubuntu OCR | Your machine, electricity, network, RAM and disk | No 24/7 promise; start for queued batches, stop after completion |

Sources: [Render](https://render.com/docs/free), [Neon official plans](https://github.com/neondatabase/website/blob/main/content/docs/introduction/plans.md), [Upstash](https://upstash.com/pricing/redis), [R2](https://developers.cloudflare.com/r2/pricing/), [Resend](https://resend.com/pricing).

Stay on the named Free plans. Do not automatically upgrade any provider or enable paid add-ons. R2's allowance is not a spending cap; if its account activation requires a billing method, the owner completes that step with knowledge of the usage charges. No billing setup is performed by this repository. Existing domain ownership may also be needed for Resend.

## 1. Neon

Follow [NEON_SETUP.md](NEON_SETUP.md): create a Free project/database, select the correct branch/role, and disable pooling in the Connect dialog.

**Copy:** direct PostgreSQL connection URI → backend `DATABASE_URL` and Ubuntu `.env.worker` `DATABASE_URL`.

Keep TLS. The app upgrades provider `sslmode=require` to `verify-full` using trusted system CAs. Do not use a `-pooler` hostname: OCR recovery needs PostgreSQL session locks. Both sides must address the same branch and database. Run the existing migrations after all external environment values are ready (step 5); no model changes are needed.

## 2. Upstash

Follow [UPSTASH_REDIS_SETUP.md](UPSTASH_REDIS_SETUP.md): create a **Free Redis** database, leave eviction disabled, and obtain its **native TCP/TLS** details.

**Copy:** host, port, username and password/token as a native URI → backend `REDIS_URL` and Ubuntu `.env.worker` `REDIS_URL`:

```text
rediss://default:PASSWORD@HOST:PORT/0?ssl_cert_reqs=required&ssl_check_hostname=true
```

Use the exact same database `/0` on both sides. Do not copy an HTTPS REST URL into Celery. The same validated URL configures broker and result backend. Business state stays in Neon; cached Celery results expire after an hour. TLS certificate and hostname verification remain enabled.

## 3. Cloudflare R2

Follow [R2_STORAGE_SETUP.md](R2_STORAGE_SETUP.md). Create a **private Standard bucket**, leave public `r2.dev` access and custom public domains disabled, and create bucket-scoped **Object Read & Write** S3 credentials.

Copy these fields into **both** backend environment and `.env.worker`:

| Cloudflare field | Application variable |
| --- | --- |
| Access Key ID | `AWS_ACCESS_KEY_ID` |
| Secret Access Key | `AWS_SECRET_ACCESS_KEY` |
| Bucket name | `AWS_STORAGE_BUCKET_NAME` |
| S3 API endpoint (HTTPS, not public bucket URL) | `AWS_S3_ENDPOINT_URL` |
| Application switch | `OBJECT_STORAGE_ENABLED=true` |
| R2 region | `AWS_S3_REGION_NAME=auto` |
| Addressing style | `AWS_S3_ADDRESSING_STYLE=path` |

The API and worker use the same private bucket. Previews/downloads retain owner/staff authentication; no public `/media/` server is added. Existing local uploads are not automatically copied to R2.

## 4. Resend

1. Create/sign in to Resend and remain on the **Free** transactional email plan.
2. Add your sending domain, copy the DNS records Resend gives you into your DNS provider, and wait for verification. See [domain setup](https://resend.com/docs/dashboard/domains/introduction).
3. Create a sending API key. Copy it into **backend only** as `RESEND_API_KEY`.
4. Copy an allowed sender identity into **backend only** as `DEFAULT_FROM_EMAIL`, e.g. `ScanToForms <noreply@yourdomain.com>`.
5. Use `EMAIL_BACKEND=apps.core.email.ResendEmailBackend`. This sends via HTTPS; no SMTP is used.

Without a verified domain, `ScanToForms <onboarding@resend.dev>` can be used only to send to the address associated with your Resend account. See [test-domain restrictions](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain). Missing/rejected email credentials can make registration fail. An API acknowledgement does not prove inbox delivery.

## 5. Render backend

Push this revision to your connected Git repository. Create **New → Web Service**, choosing that repository and your deployment branch:

| Render setting | Value |
| --- | --- |
| Name | `scantoforms-api` or your own unique name |
| Runtime | Docker |
| Instance Type | Free |
| Root Directory | Leave empty |
| Dockerfile Path | `./backend/Dockerfile.render` |
| Docker Build Context | `./backend` |
| Docker Command | Leave empty (image default) |
| Health Check Path | `/health/` |

Alternatively, **New → Blueprint** with `render.yaml` creates just the two separate application services. Do not also create duplicate services manually. The Blueprint has no databases, Key Value, worker or disk. Existing resources from an older setup are not deleted by editing this file; no account resources have been inspected or modified here.

Add all provider values from steps 1–4 to the **backend** environment. The Blueprint prompts for them using `sync: false`. Also configure:

```dotenv
EXTERNAL_SERVICES_REQUIRED=true
DJANGO_DEBUG=false
DJANGO_TRUST_PROXY=true
PROCESSING_MODE=celery
CELERY_TASK_ALWAYS_EAGER=false
WEB_CONCURRENCY=1
RUN_MIGRATIONS=true
TEST_DEPLOYMENT=true
ENABLE_LEGACY_WORKSPACE=false
ENABLE_PAYSTACK=false
MANUAL_BANK_TRANSFER_ENABLED=true
DIGITIZATION_PRICE_PER_RESPONDENT_NGN=500
SYNTHETIC_PRICE_PER_RESPONSE_NGN=1000
EMAIL_BACKEND=apps.core.email.ResendEmailBackend
RESEND_TIMEOUT_SECONDS=15
OBJECT_STORAGE_ENABLED=true
AWS_S3_REGION_NAME=auto
AWS_S3_ADDRESSING_STYLE=path
```

Set these owner-specific fields directly in Render:

| Field | What to enter |
| --- | --- |
| `DJANGO_SECRET_KEY` | Stable long random secret; Blueprint generates it, or generate locally with `python3 -c 'import secrets; print(secrets.token_urlsafe(64))'` |
| `DJANGO_ALLOWED_HOSTS` | Actual API hostname, e.g. `your-api.onrender.com`, without scheme |
| `FRONTEND_URL` | Actual frontend HTTPS origin, without trailing slash |
| `DJANGO_CORS_ALLOWED_ORIGINS` | That exact frontend HTTPS origin |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Frontend and API HTTPS origins, comma-separated |
| `BANK_NAME`, `BANK_ACCOUNT_NAME`, `BANK_ACCOUNT_NUMBER` | Your existing manual-payment settings; do not send real money for test orders |

Use the intended frontend origin initially, then correct it after step 6. Copy actual assigned URLs from Render; names can be taken. `DATABASE_SSL_ROOT_CERT` and `REDIS_SSL_CA_CERTS` are optional custom CA paths; leave them unset normally. Missing external credentials intentionally stop API startup instead of falling back to SQLite, local Redis or ephemeral uploads.

Deploy. The image runs `migrate --noinput`, `collectstatic`, then Gunicorn on Render's `PORT`. Check logs for successful migrations and visit `https://ACTUAL_API_HOST/health/` for `{"status":"ok"}`. This health check tests only the database. It does not prove Redis, R2, email or OCR.

For administrator creation, use the configured local environment and `python manage.py createsuperuser` as explained in [Neon setup](NEON_SETUP.md). Free Render services have no interactive shell. No default administrator or public bootstrap endpoint is added.

## 6. Render frontend

Create a second **Web Service** from the same repository/branch:

| Render setting | Value |
| --- | --- |
| Name | `scantoforms-web` or your own unique name |
| Runtime | Node |
| Instance Type | Free |
| Root Directory | `frontend` |
| Build Command | `npm ci && npm run build` |
| Start Command | `npm run start -- --hostname 0.0.0.0 --port $PORT` |
| Health Check Path | `/` |

Set:

```dotenv
NODE_VERSION=22
NEXT_PUBLIC_API_URL=https://ACTUAL_API_HOST.onrender.com/api/v1
NEXT_PUBLIC_DEPLOYMENT_NOTICE=Controlled beta: processing runs during operator availability and may be delayed. Use non-sensitive test files and keep your originals. Do not transfer real money for test orders.
```

**Copy:** backend public HTTPS URL + `/api/v1` → frontend `NEXT_PUBLIC_API_URL`. No trailing slash. These public variables are embedded at build time; rebuild after changing them. Never put Neon, Upstash, R2 or Resend credentials in the frontend.

**Copy back:** frontend public HTTPS origin → backend `FRONTEND_URL`, `DJANGO_CORS_ALLOWED_ORIGINS`, and the frontend entry in `DJANGO_CSRF_TRUSTED_ORIGINS`. Redeploy the backend. Open a real order URL directly and refresh it as part of validation; the Next.js runtime must serve new dynamic paths.

## 7. Ubuntu worker

Follow [REMOTE_OCR_WORKER.md](REMOTE_OCR_WORKER.md). Copy `.env.worker.example` to ignored `.env.worker`, restrict it to mode 600, and fill in:

- The **same direct Neon `DATABASE_URL`** from step 1.
- The **same native Upstash `REDIS_URL`** from step 2.
- The **same private bucket endpoint/name/credentials** from step 3.
- The backend's `DJANGO_SECRET_KEY`, copied privately from Render.
- `EXTERNAL_SERVICES_REQUIRED=true`, `OBJECT_STORAGE_ENABLED=true`, `PROCESSING_MODE=celery`, `CELERY_TASK_ALWAYS_EAGER=false`.

`OCR_ENGINE=auto` keeps PaddleOCR primary and Tesseract fallback. Use the same repository revision as the API and keep concurrency 1. Docker installs the existing OCR dependencies; the native equivalent is `celery -A config worker -l info --concurrency=1` from `backend` with the environment selected.

Start only when paid/queued work exists, process the batch, then stop gracefully. Do not deploy OCR on Render, enable eager processing, or schedule an unattended worker. Track Upstash usage during runs. The API and worker template tests prove matching configuration for supplied values; only your live checks can prove your actual secrets point to the same services.

## 8. First end-to-end test

Use [the beta acceptance checklist](RENDER_TEST_DEPLOYMENT.md) and disposable data:

1. Verify API health and admin CSS/login; register a permitted email recipient, follow verification, log in, log out and reset the password through actual inbox delivery.
2. Create one small digitization order (e.g. 2 respondents × 4 pages), upload its source files, and verify authenticated preview. Another customer and anonymous requests must not read them; anonymous R2 access must fail.
3. Test payment claim and staff verification using the existing test procedure. A customer claim alone must not unlock processing. Prepare/verify the questionnaire schema, then queue the order with the worker stopped.
4. Confirm database jobs are queued. Start the Ubuntu worker; observe real PaddleOCR or recorded Tesseract fallback, review uncertain answers, and confirm the correct two respondent rows. No fabricated OCR or readiness flags.
5. Download the permitted result and test a direct dynamic frontend URL/refresh. Redeploy the API, then verify source-file hashes and records still match R2/Neon.
6. With no active task and a dedicated disposable recovery case, verify the existing staff retry can republish eligible database jobs after lost delivery. Never flush a shared queue. Existing local PostgreSQL recovery tests also cover duplicate/active-job protection.
7. Stop the worker after the batch and record provider usage, actual URLs, deployed commit, failures and test evidence. A provider ping is not a complete end-to-end pass.

Google Forms uses generated Apps Script authorized by the form owner; no Google OAuth/API secret is needed here. Paystack is disabled; the existing manual bank-transfer flow remains. No new product functionality is introduced.

Troubleshooting: hostname errors require the actual `DJANGO_ALLOWED_HOSTS`; CORS errors require the exact frontend origin; localhost/old API requests require a frontend rebuild; persistent queued jobs require the correct worker/Upstash connection; Neon pooler errors require the direct URL; certificate errors require trusted CAs, not disabled TLS. Stop at provider limits instead of upgrading.
