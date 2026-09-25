# ScanToForms $0 Render acceptance deployment

This runbook supersedes the earlier paid-worker preparation. The owner has authorized **free resources only**. Do not upgrade a plan, attach a paid disk, or create a paid background worker without asking first. This is a disposable workflow test, not an accepted customer-data deployment. See [the live acceptance report](RENDER_LIVE_ACCEPTANCE_REPORT.md).

## Exact deployment scope

`render.yaml` declares project **ScanToForms Beta**, environment **Beta**:

| Resource | Plan | Purpose |
| --- | --- | --- |
| `scantoforms-web` | free | Node 22 / Next.js frontend |
| `scantoforms-api` | free | Existing API-only production Docker image |
| `scantoforms-beta-db` | free | PostgreSQL 16, permanent-record source of truth during the test database's lifetime |
| `scantoforms-redis` | free | Private queue with `noeviction`, persistence off |
| Celery OCR worker | NOT provisioned | BLOCKED BY FREE INFRASTRUCTURE |
| Shared persistent upload storage | NOT provisioned | BLOCKED BY FREE INFRASTRUCTURE |

All declared plans are explicitly `free`. If the workspace has exhausted its free allocation or a resource is unavailable, stop and report that; do not select a paid fallback. The API still publishes to Redis and the worker code remains separate. `PROCESSING_MODE=celery` and eager execution is off. Do not run Celery inside the API, fake OCR, or claim a manual/local run passed on Render.

Free services have cold starts, quotas and ephemeral filesystems. Free PostgreSQL expires after 30 days; record its actual expiration date and export any test records needed before expiry. Free Redis can lose queued tasks. PostgreSQL rows remain the application source of truth, but an expiring test database is not a production durability promise. Review [Render free-service limits](https://render.com/docs/free) and [the Blueprint reference](https://render.com/docs/blueprint-spec) at deployment.

## Before creating resources

1. Connect the Render integration and use only the authorized workspace. Inspect existing services, free quotas and any existing Blueprint before syncing; do not accidentally modify an unrelated project. The earlier paid blueprint was never provisioned by this workspace.
2. Deploy the current GitHub `main` revision, not the pre-refactor baseline `8704599` or the superseded paid-worker blueprint. Record the exact deployed commit and service URLs in the report.
3. Enter the secrets directly in Render: Resend key, sender, bank details and generated Django secret. Never put them in chat, source control, or browser-visible environment variables.
4. Confirm the plan review shows only free resources. Use the existing authorized workspace's project if already created; otherwise use the Blueprint's ScanToForms Beta project.
5. Keep only disposable, non-sensitive files and test identities on this deployment. Do not collect real money for these test orders. External private persistent storage is required before students entrust actual questionnaires to the service.

## Exact environment checklist

These are the names the application reads. Generic `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` are not environment aliases: use the `DJANGO_` names.

| Variable | Service | Value / source |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | API | Blueprint-generated unique secret, stable across restarts |
| `DJANGO_DEBUG` | API | `false` |
| `DJANGO_ALLOWED_HOSTS` | API | Actual API hostname, no scheme/wildcard; comma-separated if needed |
| `DJANGO_TRUST_PROXY` | API | `true` behind Render's managed HTTPS proxy |
| `DJANGO_CORS_ALLOWED_ORIGINS` | API | Exact HTTPS frontend origin, no trailing slash |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | API | Exact HTTPS API/admin and frontend origins, comma-separated |
| `FRONTEND_URL` | API | Actual HTTPS frontend origin for reset links |
| `DATABASE_URL` | API | Blueprint reference to free PostgreSQL's private connection string |
| `REDIS_URL` | API | Blueprint reference to free Key Value's private connection string |
| `PROCESSING_MODE` | API | `celery`; there is no deployed worker |
| `CELERY_TASK_ALWAYS_EAGER` | API | `false` |
| `TEST_DEPLOYMENT` | API | `true`; does not fabricate data |
| `ENABLE_LEGACY_WORKSPACE` | API | `false` |
| `ENABLE_PAYSTACK` | API | `false` |
| `MANUAL_BANK_TRANSFER_ENABLED` | API | `true`; test the existing claim/staff-verification workflow |
| `BANK_NAME` | API | Owner enters directly in Render |
| `BANK_ACCOUNT_NAME` | API | Owner enters directly in Render |
| `BANK_ACCOUNT_NUMBER` | API | Owner enters directly in Render |
| `DIGITIZATION_PRICE_PER_RESPONDENT_NGN` | API | `500` initial beta rate, configurable |
| `SYNTHETIC_PRICE_PER_RESPONSE_NGN` | API | `1000` initial beta rate, configurable |
| `USE_S3_STORAGE` | API | `false` for disposable testing only; no bucket exists |
| `MEDIA_ROOT` | API | `/app/media`, ephemeral; never public-routed |
| `EMAIL_BACKEND` | API | `apps.core.email.ResendEmailBackend` |
| `RESEND_API_KEY` | API | Owner supplies secret in Render; no invented key |
| `DEFAULT_FROM_EMAIL` | API | Sender permitted by Resend, e.g. an address on the owner's verified domain |
| `RESEND_TIMEOUT_SECONDS` | API | `15` |
| `NODE_VERSION` | Frontend | `22` |
| `NEXT_PUBLIC_API_URL` | Frontend build/runtime | `https://<actual-api-host>/api/v1` |
| `NEXT_PUBLIC_DEPLOYMENT_NOTICE` | Frontend build/runtime | Blueprint's visible disposable-test, unavailable-OCR, possible-file-loss and no-real-payment notice |

Render supplies `PORT`. The API uses one Gunicorn process by default (`WEB_CONCURRENCY=1`). `RUN_MIGRATIONS` defaults to true; keep one API instance. Optional existing upload/count limits remain validation limits, not measured OCR capacity: `MAX_UPLOAD_BYTES`, `MAX_PDF_PAGES`, `MAX_ORDER_RESPONDENTS`, `MAX_ORDER_PAGES`, `MAX_SYNTHETIC_RESPONSES`. No SMTP, S3, Google OAuth or Paystack secrets are required for this free deployment. Only the API calculates prices; existing orders retain their price snapshot.

## Resend setup and acceptance

The new Django mail backend posts existing verification/reset messages to `https://api.resend.com/emails` over HTTPS. It has a timeout, requires a provider acknowledgement, and fails rather than reporting a rejected message as sent. It does not add a queue dependency or an email SDK. No SMTP ports are used. A successful API response means accepted by Resend, not proven inbox delivery. [Resend send-email API](https://resend.com/docs/api-reference/emails/send-email).

The owner creates a Resend API key and configures `RESEND_API_KEY` securely. For real recipients, verify an owned sending domain using the DNS records provided by Resend, then set `DEFAULT_FROM_EMAIL` to an allowed sender on that domain. Domain ownership/setup is an owner action, not something this repository can invent. [Resend domain verification](https://resend.com/docs/dashboard/domains/introduction).

Without a verified domain, Resend's test sender is restricted to the account owner's email address. Do not claim student delivery works from a self-send test; domain verification is needed for arbitrary recipients. [Resend test-domain restrictions](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain).

Live checks: register an allowed address; inspect actual inbox delivery; follow verification; log in; log out; request reset; receive and use reset link; confirm new login and old credential/session rejection. Missing credentials/provider rejection must not be described as delivered mail. Registration is transactional and rolls back on a transport failure. No mail was sent by the mocked transport tests.

## API, database and admin startup

The unchanged API entrypoint runs migrations and `collectstatic`, then Gunicorn. Confirm `/health/` returns 200, but remember it checks only a database query. Also verify `/admin/login/` and its CSS, frontend assets, API CORS, authenticated notifications and order requests. Redis PONG proves only broker connectivity; no worker reply is expected in this configuration.

Free web services do not provide a Render shell. To create the staff operator, run the existing Django `createsuperuser` management command locally against the test PostgreSQL database using its external connection URL in a protected local environment. Temporarily allow only the operator's public IP in the database's external access list, then remove it after setup. The Blueprint initially blocks all external database access. Never commit the connection URL or account password; do not use test-suite seeded credentials. This uses the existing management command, not a new unauthenticated bootstrap route. No existing/customer database may be reset.

## Private uploads and persistence

Source downloads retain existing authentication and owner/staff checks. Do not publish `/media/` or expose a public file server. Local source files can disappear on spin-down, restart or redeploy; database metadata surviving does not mean the file survived. The configured frontend notice warns users before they upload.

Only disposable test files are permitted. Keep originals locally and assume re-upload may be necessary. A controlled restart can demonstrate the limitation, but does not certify persistence even if a particular file happens to survive once. Record the persistence acceptance status as **BLOCKED BY FREE INFRASTRUCTURE**, never PASSED.

A private shared S3-compatible bucket is needed before accepting irreplaceable/customer questionnaires and before a separate worker can read API uploads reliably. No provider or bucket has been added. Cloudflare R2 can be evaluated later; first present its current free-tier terms, required account/billing setup, privacy controls and configuration to the owner. Do not assume an account or silently enable a provider.

## What can be accepted at $0

Test the landing page, register/login/logout/reset (with Resend), two order forms, beta prices, private disposable uploads, completeness, payment claim, staff-only verification/rejection, audit, notifications and operator inspection. A 2×4 order should cost NGN 1000; a 10-response synthetic request should cost NGN 10000. Those are configured beta totals, not frontend constants. Use explicit test orders without real transfers.

Validate User A/User B isolation across orders, questionnaire/document/source endpoints, answers/page movement, exports/scripts and synthetic results. An unpaid request remains locked. Clicking I HAVE PAID must only record PAYMENT_SUBMITTED; customer self-verification must fail.

The digitization process endpoint can queue a paid job, but it will not be consumed without a worker. Normally leave test orders PAID; if testing dispatch, record the QUEUED job as unexecuted, do not leave an unexplained processing claim. Never mark READY without real reviewed data. Free Redis loss can remove the queued message even when the PostgreSQL job exists.

Synthetic request/payment/operator inspection can be tested. Under celery mode, the internal generator also needs a worker. Its queued completion is blocked. Existing attachment/review/result delivery can be tested only with a legitimate completed dataset prepared via an explicitly agreed operator procedure, not invented results or manipulated confirmation flags. Do not silently change processing mode to force fulfillment.

Result pages and Google instructions may be inspected, but final CSV/XLSX/script delivery needs an eligible paid/reviewed result. Separate a UI inspection, a local pass and a real Render end-to-end pass. The existing Playwright script starts local services in manual mode; it does not test Render.

## Real OCR and Google gates

No clean shared-storage path currently exists for a local worker to consume this deployment's ephemeral uploads. A future test-only local Celery worker could use the existing broker/database plus private shared storage, but would need network access controls and reliable object access. That proposal must be explained and agreed before implementation; it would still be **local worker execution**, not a Render worker pass. No tunnel, inline worker or other workaround is implemented now.

Keep Google acceptance **TESTING REQUIRED**. Do not request the disposable Form URL until an eligible dataset/script and all prerequisites are ready. At that point say **GOOGLE FORM ACCEPTANCE TEST READY**, ask for the Form EDIT URL, and let the owner run/authorize the generated script. Do not request Google credentials or add OAuth. Record exact expected/actual counts, title/option mapping, text/multiple-choice/checkbox/scale behavior and duplicate prevention. Synthetic Google submission remains blocked.

## Reporting categories

Use exactly the relevant evidence category: **PASSED ON RENDER**, **PASSED LOCALLY ONLY**, **BLOCKED BY FREE INFRASTRUCTURE**, **REQUIRES OWNER ACTION**, or **REQUIRES EXTERNAL SERVICE**. Keep actual test failures explicit too. A free frontend loading is not acceptance of OCR, persistence, email or Google delivery. Do not invite students with real data or accept real payments while those promises remain unverified.
