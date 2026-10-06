# External-services beta acceptance checklist

Current architecture: **ZERO-BUDGET / FREE-TIER CONTROLLED BETA**. This replaces the older Render-managed PostgreSQL/Key Value runbook. Setup is in [RENDER_SETUP.md](RENDER_SETUP.md), in the required provider order. Historical acceptance reports are not evidence of this topology working live.

## Configuration before live testing

- Render Blueprint contains only two Free web services; no datastore, disk or background worker.
- Frontend uses Node/Next.js runtime for dynamic order/review/questionnaire paths.
- API and worker use the same **direct Neon database** with verified TLS, **Upstash native `rediss://` database `/0`**, and **private R2 Standard bucket**. Both set `EXTERNAL_SERVICES_REQUIRED=true`.
- Keep `PROCESSING_MODE=celery`, `CELERY_TASK_ALWAYS_EAGER=false`, concurrency 1 and `OCR_ENGINE=auto` (PaddleOCR primary, Tesseract fallback).
- API alone holds Resend key/sender, bank settings, frontend origins and pricing. No secrets are placed in `NEXT_PUBLIC_*` variables.
- Existing migrations are applied once through API startup (or a coordinated local command), then the matching worker revision starts. No database resets or new product functionality.
- Review each provider's quotas; remain on the selected free plans. Stop work at limits instead of upgrading. R2's free allowance is not a spending cap.

## Live checks after credentials are supplied

1. **Database:** run the SELECT/TLS check in [Neon setup](NEON_SETUP.md), confirm migrations, and verify API `/health/`. Health only checks a database query.
2. **Queue:** run one secure ping from [Upstash setup](UPSTASH_REDIS_SETUP.md); use a bounded worker session, not continuous monitoring. A ping does not prove delivery.
3. **Email/auth:** receive actual Resend verification and reset emails, follow links, check login/logout and old-password rejection. Provider acceptance alone is not inbox delivery.
4. **Private storage:** upload disposable printed sources through a permitted order. Owner/staff downloads work; anonymous/other-user access and public R2 URLs fail. The browser uses authenticated API streams. Verify the bucket's public access switches in Cloudflare.
5. **Payment gate:** an upload or payment claim does not run OCR or unlock results. Customer attempts to verify/process/retry must fail. Staff uses the existing verification workflow with a clearly identified test order; do not transfer real money.
6. **Real processing:** prepare/verify schema for a small 2-respondent × 4-page case, queue with worker off, start Ubuntu, and record actual engine, job IDs, queue receipt, duration, failures and database results. Exactly two logical respondent rows must result. Correct uncertain grouping/answers and confirm reviewed results before delivery.
7. **Frontend:** navigate to a newly created order and review page, open each directly and refresh. API requests must use the public backend URL, not localhost. Test actual CORS and secure admin CSS/login.
8. **Persistence:** compare source hashes before/after API redeploy and worker restart. Confirm records remain in Neon and private files in R2. Database metadata alone does not prove the file survived.
9. **Recovery:** in a dedicated disposable case with no active task, test staff retry of eligible durable OCR jobs after missing delivery. Never flush a shared broker. Confirm active/finished jobs are not duplicated and recovery is audited. This route covers digitization OCR, not synthetic-job recovery.
10. **Finish:** stop the worker with warm shutdown, record quota use, errors and remaining limitations. Eight real pages do not establish 480-page capacity. Google Forms authorization/execution remains a separate owner-run test with a disposable Form.

## Evidence to record

| Item | Evidence required |
| --- | --- |
| Revision / URLs | Exact deployed commit, frontend URL, backend URL |
| Provider setup | Selected free plans, non-secret endpoint/bucket identities, remaining quotas |
| PostgreSQL | Migration result and verified TLS SELECT |
| Redis | TLS ping and real worker receipt; command usage before/after |
| R2 | Private access controls, owner/other-user checks, matching file hashes |
| Resend | Actual inbox delivery and working verification/reset links |
| OCR | Real engine, job IDs, reviewed results and correct respondent count |
| Recovery | Eligible republish plus duplicate/active-job protection |
| Shutdown | Worker stopped after processing |

Use precise statuses: **PASSED LOCALLY**, **PASSED LIVE**, **AWAITING CREDENTIALS**, **FAILED**, or **LIMIT REACHED**. Do not describe offline URL parsing/signing tests as a provider connection, a local PostgreSQL test as Neon acceptance, or a worker ping as completed OCR.
