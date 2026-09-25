# ScanToForms Render live acceptance report

Assessment: 2026-09-25. **Current constraint: $0; free Render resources only.** This supersedes the prior proposed paid-worker deployment. No paid worker, paid disk or object-storage service is authorized. The product remains the existing two-service MVP.

**Overall verdict: NOT FULLY ACCEPTED.** Deployment awaits Render connection and owner configuration. Live OCR and upload persistence are blocked by infrastructure. Real Google execution remains **TESTING REQUIRED** and is deferred until its prerequisites are ready. Local passes are not Render passes.

Evidence categories: **PASSED ON RENDER**, **PASSED LOCALLY ONLY**, **BLOCKED BY FREE INFRASTRUCTURE**, **REQUIRES OWNER ACTION**, **REQUIRES EXTERNAL SERVICE**. No capability currently has PASSED ON RENDER evidence.

## 1. Render services actually deployed

**REQUIRES OWNER ACTION.** No Render services have been created or observed through authenticated account access. The integration still reports unconnected. Existing account resources and any pre-existing Git deployment automation cannot be inspected.

The prepared Blueprint defines project **ScanToForms Beta**, environment **Beta**, with only explicitly free resources: Next.js web, Django web, PostgreSQL 16 and private Key Value. No worker, persistent disk or object-store resource is declared. If free quotas are unavailable, stop rather than upgrade. Earlier preparation was published to GitHub; deploy the current free-only `main`, not the superseded paid blueprint or original pre-refactor application.

## 2. Exact environment configuration categories

See the complete [environment checklist](RENDER_TEST_DEPLOYMENT.md#exact-environment-checklist). Categories: Django secret/hosts/HTTPS; browser CORS/CSRF/frontend origin; PostgreSQL; private nonpersistent Redis; existing Celery mode with eager tasks off; ephemeral private media; Resend HTTPS key/sender; manual bank settings; configurable prices; frontend API URL and disposable-test notice.

Beta rates in the deployment environment are NGN 500 per digitized respondent and NGN 1000 per synthetic response. No frontend price constants were added. Bank details and `RESEND_API_KEY` must be entered directly in Render, not chat. No SMTP or invented credentials are configured. Use actual `DJANGO_` environment names, not generic aliases.

## 3. Persistent-storage configuration

**BLOCKED BY FREE INFRASTRUCTURE.** The owner has no bucket or persistent disk. `USE_S3_STORAGE=false` and `MEDIA_ROOT=/app/media` intentionally use disposable local files. Uploads can disappear after restart, redeploy or spin-down. The frontend displays this limitation and asks users to keep originals and use non-sensitive test files.

Existing owner/staff source-file authorization remains intact. No public media route was added. Database metadata is not a substitute for a missing source file. A private shared S3-compatible bucket is needed before students entrust actual questionnaires to this deployment and before a separate worker reliably accesses the files. No new storage provider was implemented. An R2/free-tier proposal and its account setup would require a separate owner decision.

## 4. API URL

**REQUIRES OWNER ACTION — unknown.** No deployed URL is available. `/health/` checks a database query only. It does not validate email, files, Redis or worker execution. Root `/` is not the configured Django health endpoint.

## 5. Frontend URL

**REQUIRES OWNER ACTION — unknown.** Set the actual API URL ending `/api/v1` before building. The build must include the visible deployment notice. Neither localhost defaults nor a successful local build establish a live frontend.

## 6. Database status

**REQUIRES OWNER ACTION.** Free PostgreSQL 16 is declared, not provisioned. The existing API entrypoint applies migrations and collects static files. PostgreSQL remains the source of truth for users, orders, payment/audit records and results while the test database exists. Free database expiration prevents any indefinite durability claim; record its actual expiry after creation. Do not reset an existing database. [Render free limits](https://render.com/docs/free).

## 7. Redis status

**REQUIRES OWNER ACTION.** Free Key Value is declared with private access, `noeviction`, and persistence off. No PONG has been observed. Its queue/results are not permanent records. If it restarts, a PostgreSQL OCR job may remain while its queue message is lost. The existing operator recovery limitations remain; no durable queue guarantee is claimed.

## 8. Worker status

**BLOCKED BY FREE INFRASTRUCTURE.** No Render worker is provisioned. The architecture remains API → Redis → Celery worker → OCR. The worker code/image stages are retained; no inline worker, eager execution, fake OCR or free-service workaround was added. A paid digitization job may queue but will not be consumed here. A locally completed task must not be reported as a Render worker pass.

## 9. Authentication test result

**PASSED LOCALLY ONLY; live delivery REQUIRES EXTERNAL SERVICE and owner configuration.** Existing account flows now have an optional Django backend that sends through Resend's HTTPS API. Local tests cover request construction, provider rejection/rate-limit/timeouts, missing credentials, header injection, acknowledgement validation, transactional registration rollback and verification/reset completion.

The new transport is tested with mocked HTTP, not a real API key or inbox. Real register/login/logout/reset request/reset completion remain unrun on Render. A Resend acknowledgement is not proof of delivery. The owner must set the key and sender; arbitrary customer recipients require a verified sending domain. The Resend test domain is limited to the account owner's address. [Resend restrictions](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain), [domain verification](https://resend.com/docs/dashboard/domains/introduction).

## 10. Digitization test result

**PASSED LOCALLY ONLY; live order/upload tests REQUIRES OWNER ACTION.** The proposed small live case remains 2 respondents × 4 pages = 8 physical pages and 2 logical responses. At the configured rate its total is NGN 1000. No such Render order/upload was created. Free deployment can test setup, completeness, authorization and payment states using disposable sources. The real OCR portion cannot pass without a worker/storage solution.

## 11. OCR result

**PASSED LOCALLY ONLY / BLOCKED BY FREE INFRASTRUCTURE.** Prior local real PaddleOCR and Tesseract smoke tests processed one printed page per engine. No deployed OCR ran. No fabricated OCR results or manual-mode substitution was used. A future local worker connected to the same broker/database would still need reliable shared source storage, which is absent. No proposed zero-cost workaround has been implemented.

## 12. Grouping result

**PASSED LOCALLY ONLY.** Existing tests cover ordered pages, missing/duplicate/out-of-order logical pages and 480 page records representing 120 respondents. This is not 480-page real OCR throughput. A live eight-page grouping inspection remains unrun. Arbitrarily shuffled respondent pages and combined multi-respondent PDFs remain outside the reliable upload flow.

## 13. Manual review result

**PASSED LOCALLY ONLY.** Local correction/confirmation integrity regressions pass. No paid, processed Render result was available to review. The real acceptance check must correct an answer, reaggregate/regroup, preserve that correction, invalidate stale confirmation and reconfirm before final delivery. No READY/CONFIRMED flags were manufactured to bypass those prerequisites.

## 14. Payment workflow result

**PASSED LOCALLY ONLY; Render REQUIRES OWNER ACTION.** Existing claim → PAYMENT_SUBMITTED → staff verification → PAID logic is unchanged. The customer's claim never unlocks processing/results and customers cannot self-verify. No real transfer was requested or performed. Bank values belong in Render settings. Use explicitly identified test orders and audit notes for workflow acceptance; these do not establish real bank reconciliation or commercial readiness.

## 15. CSV/XLSX result

**PASSED LOCALLY ONLY.** Existing final-data, one-row-per-respondent and spreadsheet-injection tests pass. No Render result download occurred. Live final export requires legitimate reviewed/confirmed data, not a bypassed readiness state. The free deployment can expose UI/instructions; successful final delivery remains a separate unperformed check.

## 16. Google Apps Script generation result

**PASSED LOCALLY ONLY.** Existing mapping, paid/final-data gating, copy/download and instructions code remains. No eligible dataset/script was generated on Render. Standard Form edit URLs/raw IDs are supported by validation; forms.gle and published `/d/e/` links remain rejected. No OAuth, Form import, direct API response creation or ownership claim was added.

## 17. REAL Google Form execution result

**TESTING REQUIRED / REQUIRES OWNER ACTION / REQUIRES EXTERNAL SERVICE.** Zero submissions were made. The owner will supply a disposable Form EDIT URL and personally authorize/run Apps Script only when prerequisites are ready. Do not request that URL prematurely. At that gate say **GOOGLE FORM ACCEPTANCE TEST READY** and ask for the edit URL, never Google credentials.

Required evidence remains 5–10 known disposable test responses, correct title/item/option mapping, exact response count and duplicate checks using previewMapping/startSubmission/continueSubmission/submissionStatus. Text, multiple-choice, checkbox and scale each need actual tests. Grids, dates/times/durations, ratings and special constraints remain unvalidated; unsupported types must be recorded. File-upload question submission and public synthetic Google submission remain unsupported. No general compatibility claim follows from one successful form.

## 18. Synthetic order result

**PASSED LOCALLY ONLY; live request/payment REQUIRES OWNER ACTION.** One blank template plus 10 requested responses costs NGN 10000 at the beta rate. Request upload, pricing, payment claim, staff verification and operator inspection can be tested without OCR. No Render synthetic order was created.

The existing internal generator also dispatches to Celery in this configuration, so queued generation cannot complete without a worker. An operator can use existing result-attachment functionality only with a legitimate completed BotRun/dataset and proper ownership/review. No dataset was fabricated or copied into a human classification. Supported synthetic CSV must retain SYNTHETIC TEST DATA. Public synthetic Google submission remains blocked.

## 19. Notification result

**PASSED LOCALLY ONLY.** No live notification feed/count was observed. Payment verified/rejected, processing, needs-attention and ready messages are database records. Test ownership and actual unread count after real state changes. A processing/queued notification does not prove a worker ran; a ready notification requires legitimate fulfillment. These are not email-delivery tests.

## 20. Persistence/redeploy result

**BLOCKED BY FREE INFRASTRUCTURE — NOT PASSED.** No live restart occurred. Local Render uploads are explicitly disposable; source loss is expected to be possible. A single restart where a file survives would not establish durable storage. PostgreSQL and free Redis have their own lifecycle limits. No public/customer persistence promise is appropriate.

## 21. Cross-user security result

**PASSED LOCALLY ONLY; Render REQUIRES OWNER ACTION.** Existing ownership tests pass, but no deployed User A/User B endpoint attempts occurred. Live checks must cover orders, questionnaires, source images, answers, page moves, exports, scripts, synthetic results and notifications, including known IDs. Authorized staff access stays explicit. Free local storage does not justify relaxing authentication or publishing `/media/`.

## 22. Observed resource limitations

No Render timing, memory, restarts, cold-start behavior or OCR throughput was observed. There is no worker to measure. Free web storage and Redis are nondurable; the database expires. The earlier candidate paid worker sizing was removed and is not an authorized deployment. No 480-page capacity estimate is made.

Free Render web services lack shell access. Operator creation uses the existing local Django management command against the isolated test PostgreSQL database, with a temporarily restricted operator-IP access rule and protected connection credentials. No bootstrap admin endpoint/default password was added.

## 23. Failures discovered

- The earlier prepared blueprint required paid API/worker/queue resources and an unavailable private bucket; it contradicted the owner's new $0 constraints and has been replaced.
- SMTP was unsuitable for this free deployment and is replaced in Render configuration by the requested Resend HTTPS backend.
- No Render authorization is available yet; no live account, service or external delivery failure could therefore be reproduced.
- Adding account transport tests exposed shared auth throttle-cache state in the test suite. The new fixture now clears its test cache before/after use. Production throttle rules were not changed.
- Queue dispatch without a consumer, ephemeral media and database expiry are explicit limitations, not hidden successful processing/persistence.

## 24. Fixes made and validation

Changed only deployment necessities:

- `render.yaml`: named beta project, free API/frontend/PostgreSQL/Key Value, no worker/disk/bucket, beta rates as environment values, Resend settings, ephemeral-media/test notice.
- `backend/apps/core/email.py`: Django email backend for Resend HTTPS; no new dependency or OCR architecture change.
- `backend/config/settings.py` and `.env.example`: key/timeout settings and safe local configuration examples; no secrets.
- `backend/tests/test_resend_email.py`: 11 focused transport/account tests with mocked network calls.
- `frontend/app/layout.tsx`: environment-driven disposable-test notice, no product redesign.
- Deployment guide and this report: revised evidence and owner/infrastructure gates.

Current validation: **90 backend tests passed on SQLite (12.56 s) and 90 passed on PostgreSQL 16 (22.35 s)**, including 11 new Resend cases. Ruff, Django check, migration consistency, frontend ESLint, TypeScript, Next.js production build, free-only Render schema checks, Compose validation and diff whitespace checks passed. The configured warning was also verified in the production HTML for landing, digitization, synthetic and registration pages. The isolated PostgreSQL container was removed afterward; no existing database was reset. No models/migrations were added. Previous local browser and real-engine OCR evidence remains historical; none is relabelled Render acceptance. Resend network calls were mocked and no email was actually delivered by these tests.

## 25. Remaining blockers

1. Connect Render, select the authorized workspace, confirm free quotas and create the free-only deployment; record exact deployed revision and URLs.
2. Owner supplies Resend secret/sender and bank settings directly in Render; verify a sending domain for arbitrary student email. Configure exact allowed hosts/origins/frontend API URL.
3. Create a real staff account securely and execute free-scope live acceptance plus cross-user checks with disposable data.
4. Persistent private shared source storage and a correctly operated worker remain infrastructure gates; neither is solved by this free deployment.
5. Real final-data delivery and Google execution need their prerequisites and the owner's manual Form test. No request for the Form URL has been made at this stage.

## Capability matrix

| Capability | Local | Render | Real External Test | Verdict |
| --- | --- | --- | --- | --- |
| Landing page | Build passed | Not run | Not observed | REQUIRES OWNER ACTION |
| Registration | Backend passed | Not run | Resend inbox not tested | REQUIRES EXTERNAL SERVICE |
| Login | Local regressions passed | Not run | Not observed | REQUIRES OWNER ACTION |
| Password reset | Resend transport/account tests passed | Not run | Real email/link not tested | REQUIRES EXTERNAL SERVICE |
| Order creation | Local regressions passed | Not run | Not observed | REQUIRES OWNER ACTION |
| Manual payment | Local regressions passed | Not run | No transfer/reconciliation | REQUIRES OWNER ACTION |
| Digitization upload | Local regressions passed | Not run | Only ephemeral storage planned | REQUIRES OWNER ACTION |
| OCR | Prior real engine smoke passed | No worker | Not run | BLOCKED BY FREE INFRASTRUCTURE |
| Page grouping | Local regressions/480-page model passed | Not run | No live OCR run | PASSED LOCALLY ONLY |
| Review | Local regressions passed | Not run | No live corrected result | PASSED LOCALLY ONLY |
| CSV | Local regressions passed | Not run | No live download | PASSED LOCALLY ONLY |
| XLSX | Local regressions/prior browser passed | Not run | No live download | PASSED LOCALLY ONLY |
| Apps Script generation | Local regressions/prior browser passed | Not run | No eligible deployed result | PASSED LOCALLY ONLY |
| Google submission | Generator tests only | Not run | TESTING REQUIRED | REQUIRES EXTERNAL SERVICE |
| Synthetic order | Local regressions passed | Not run | No live request/fulfillment | REQUIRES OWNER ACTION |
| Notifications | Local regressions/prior browser passed | Not run | Not observed | REQUIRES OWNER ACTION |
| File persistence | No remote durable store | Ephemeral by design | Not accepted | BLOCKED BY FREE INFRASTRUCTURE |
| Cross-user isolation | Local regressions passed | Not run | Deployed endpoints untested | PASSED LOCALLY ONLY |

## Readiness answers

1. **Is Render suitable for this controlled beta?** Suitable in principle for the constrained disposable workflow test. It has not been live-validated, and this $0 configuration cannot satisfy worker/persistence acceptance.
2. **Can we invite 3–5 students?** Not yet. First deploy and verify email, authentication, authorization and the small free-scope flow. Any later invitation at this configuration must explicitly permit only disposable non-sensitive test data; real questionnaires need private persistent storage first.
3. **Can we safely accept money yet?** No paid-service acceptance is established. The notice says not to transfer real money for test orders. Verified delivery/persistence, operator reconciliation and the advertised Google outcome are still missing.
4. **Has a real Form been populated?** No. TESTING REQUIRED until the owner runs the prepared script and verifies results.
5. **What is safe to advertise?** A disposable website workflow test only. Clear printed, ordered questionnaires with operator review remain the narrow candidate service, not live-certified automated OCR/Google delivery.
6. **What stays beta/unsupported?** Unmeasured handwriting/check/circle/tick/Likert recognition; shuffled respondent identification; combined multi-respondent PDFs; untested Google grids/date/time/rating/constraints. Google file-upload submission and public synthetic Google submission are unsupported.
7. **Maximum actual batch tested?** Render zero pages. Prior real local OCR smoke one page per engine; local model/grouping regression 480 pages/120 respondents. No 480-page real OCR capacity claim.
8. **What changes before scaling?** First obtain private shared persistent storage and a proper worker, then measure real small-job memory/timing/recovery. Durable queue/database lifecycle, backups and operator capacity need validation before scaling.
9. **First paid pilot blockers?** Live access/configuration, real email and isolation, durable private sources, dependable processing/fulfillment, final-result delivery, bank reconciliation and successful owner-run Google acceptance.
10. **Broader launch blockers?** All pilot gates plus representative OCR/question-type evidence, measured capacity, recovery/monitoring/backups and support operations. The free workflow test cannot establish those.
