# ScanToForms Render live acceptance report

Assessment date: 2026-09-25. Application baseline: `7ac030a`.

**Verdict: BLOCKED — not deployed or live-accepted from this workspace.** The local MVP is a controlled-beta candidate. There is no evidence yet that its complete workflow works on Render or submits correctly to a real Google Form. Deployment preparation is not deployment acceptance.

This report separates previously completed local validation from source inspection, this session's configuration checks, and external execution. `NOT RUN` means no live attempt was possible; it does not mean the application failed that test. No customer data, real bank transfer, or Google response was created in this session.

## 1. Render services actually deployed

**None deployed by this session. Existing account resources are unknown.** No authenticated Render integration, Render CLI configuration, Render credential, workspace ID, or deployment URL was available. The available Render integration was suggested for connection; it was not connected at the time of this report. No resource charges were incurred here.

The original blueprint described only an API and frontend in manual-transcription mode. The prepared blueprint now describes:

| Resource | Configuration prepared | Actual state |
| --- | --- | --- |
| `scantoforms-api` | Docker web service, existing `starter` plan, database health check | Not deployed/observed |
| `scantoforms-web` | Node 22 Next.js web service, `free` plan | Not deployed/observed |
| `scantoforms-ocr` | Docker worker, `2c-4g` candidate, concurrency 1 | Not deployed; capacity unmeasured |
| `scantoforms-redis` | Private Key Value, `256mb`, persistent, no eviction | Not deployed/observed |
| PostgreSQL | External `DATABASE_URL` supplied to API and worker | Not provisioned by blueprint |
| Private object storage | External shared S3-compatible bucket | Not provisioned by blueprint |

Candidate plans must be checked against the selected workspace's availability and budget. The repository branch is `main`. Initial remote inspection returned `8704599cea521e39943f762c052b806315de1e37`, the pre-refactor baseline; the focused MVP commits were local only. A shorter parallel query timed out, but the original query completed. Publishing the current MVP is a prerequisite to deploying from that branch. A Render deploy must record its actual commit SHA, not assume it contains local changes.

## 2. Exact environment configuration categories

The complete variable-by-variable checklist, including values, service scope and optional limits, is in [RENDER_TEST_DEPLOYMENT.md](RENDER_TEST_DEPLOYMENT.md#exact-environment-variable-checklist). Categories are:

- Django: secret, `DJANGO_DEBUG=false`, allowed hosts, trusted proxy and HTTPS settings.
- Browser security: exact `DJANGO_CORS_ALLOWED_ORIGINS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`.
- Persistence: shared PostgreSQL `DATABASE_URL`; private bucket name, region, endpoint and credentials.
- Queue/worker: `REDIS_URL`, `PROCESSING_MODE=celery`, eager tasks off, CPU OCR engine and model-cache path, worker build target.
- Business: actual bank name/account holder/account number; positive NGN digitization and synthetic rates; manual bank transfer enabled.
- Email: real SMTP host, STARTTLS port/login/secret and verified sender.
- Frontend: Node 22 and build-time `NEXT_PUBLIC_API_URL` ending in `/api/v1`.
- Scope: legacy workspace and Paystack off; existing code keeps organizations, public Bot Lab, OAuth and WhatsApp disabled.

Bare `DEBUG`, `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` are not recognized environment aliases in this application. Use the `DJANGO_` names. Bank details and rates were not fabricated. No secrets were added to tracked files.

## 3. Persistent-storage configuration

**Prepared, not verified against a real bucket.** Both services are configured to use the same private S3-compatible storage. The task opens the Django storage object and copies it into a temporary directory for OCR, so it does not require the API's local filesystem. Source records store the object key in PostgreSQL. Generated script content lives in PostgreSQL; CSV/XLSX are regenerated from stored records.

Application source routes are authenticated and owner/staff scoped. There is no unrestricted Django `/media/` route. However, `default_acl=None` and signed-URL settings do not override an incorrectly public bucket policy. Actual object privacy remains untested. Required evidence: owner download succeeds; User B and unauthenticated source downloads fail; unsigned bucket-object access fails; API and worker storage reads produce the same SHA-256 before and after redeploy.

No Render disk is configured. A disk belongs to one service instance and cannot supply a shared API/worker filesystem. Shared persistent object storage is required for this architecture. [Render disk restrictions](https://render.com/docs/disks).

## 4. API URL

**Unknown — no deployed URL provided or discovered.** Expected health path is `/health/`, not the API root. The health handler checks PostgreSQL connectivity with `SELECT 1`; it does not check Redis, a worker, storage, SMTP or OCR.

## 5. Frontend URL

**Unknown — no deployed URL provided or discovered.** Set the actual API URL before `next build`, then rebuild if it changes. The code's localhost fallback must not be used in a Render build. Verify frontend assets, CORS and authentication from the actual HTTPS browser origin.

## 6. Database status

**Render: NOT RUN.** The blueprint requires a PostgreSQL URL and does not create a database. The API's existing startup script runs migrations and static collection before Gunicorn; the worker does neither. Confirm all migrations applied before queuing work. Keep the tested PostgreSQL 16 version where available or explicitly validate the version provisioned. Local evidence is the prior 79-test PostgreSQL 16 run; no live database, migration history, backup or restore was inspected.

## 7. Redis status

**Render: NOT RUN.** The prepared private Key Value resource uses `noeviction` and `journal-snapshot` persistence. Both services reference its connection string. Verify a Redis PONG from the API and a Celery worker reply separately. A broker PONG alone cannot prove tasks are consumed. Render documents Key Value persistence and Blueprint resource references in its [Blueprint reference](https://render.com/docs/blueprint-spec).

## 8. Worker status

**Render: NOT RUN.** The worker selects the existing `ocr-production` Docker stage using the non-secret `RENDER_TARGET` build argument. It contains the existing pinned PaddleOCR/PaddlePaddle/PaddleX dependencies and Tesseract and runs Celery at concurrency 1. Render's translation of environment values into build arguments is documented in [Docker on Render](https://render.com/docs/docker).

Required live proof: worker startup/registration, shared bucket access, actual queued task IDs received, persisted OCR results, final job status and engine. No worker image was fully built this session, no real job traversed a deployed broker, and no Render worker resource measurements exist.

## 9. Authentication test result

**Live register/login/logout/reset request/reset completion/email delivery: NOT RUN.** Previous local browser and backend tests passed. No SMTP credentials, deployed host or inbox access was available. Neither the console email backend nor a test mail backend qualifies as delivered email. Django Admin login and its static assets also remain untested on Render.

## 10. Digitization test result

**Live 2 respondents × 4 pages = 8 pages: NOT RUN.** The source and local tests support ordered image slots and one complete PDF per respondent. Existing uploads create documents/pages without queuing OCR. An operator must verify a complete questionnaire schema before starting paid processing.

Required live evidence: one test order reference, eight distinct source documents/page slots, correct price snapshot, completeness, zero pre-payment OCR jobs, and two logical respondents after actual OCR. Do not submit a shuffled pile or a combined multi-respondent PDF as a supported grouping workflow.

## 11. OCR result

**Live OCR: NOT RUN.** Prior real local smoke tests recognized printed text using both PaddleOCR and Tesseract, one page per engine. That is not an eight-page queued pipeline result or measured questionnaire accuracy. The configured `auto` mode may use real Tesseract fallback; record the actual engine from every job. No mocked OCR or manual transcription was substituted for the required live test.

## 12. Grouping result

**Live grouping: NOT RUN.** Local regressions cover 8 ordered pages/2 respondents, missing/duplicate/out-of-order logical pages, and a 480-page/120-respondent data-model case. Those are not Render OCR throughput tests. Live acceptance must inspect both respondents, all four assigned logical pages each, classification warnings and duplicate/missing-page handling.

## 13. Manual review result

**Live review: NOT RUN.** Earlier local tests cover correction preservation, reaggregation, confirmation invalidation and final-data filtering. The live test must deliberately edit an answer, trigger a material regroup/reaggregation, verify the correction remains and confirmation is invalidated, then approve and confirm again. Any unresolved blocking issue must prevent READY/final delivery.

## 14. Payment workflow result

**Live payment workflow and bank reconciliation: NOT RUN.** Earlier local tests cover price snapshots, payment claim without unlock, staff-only verification, rejection and audit. The live test needs configured real bank instructions/rates and separate customer/operator accounts. User A's claim must leave processing/results locked; only staff can verify after independently checking the transfer. No actual transfer was made, and no bank receipt was claimed as verified.

## 15. CSV/XLSX result

**Live download/content/ownership: NOT RUN.** Prior local tests cover final human responses, one respondent per row, and spreadsheet formula protection; the browser test downloaded XLSX. Verify live CSV and XLSX contain exactly the two final respondents and known corrected values, exclude incomplete data, neutralize formula prefixes, and deny another user's request. Synthetic delivery uses labelled CSV, not an unlabelled human export.

## 16. Google Apps Script generation result

**Live generation/copy/.gs download/instructions: NOT RUN.** These paths were validated locally. The script targets an existing form; ScanToForms does not create a form or verify ownership. Standard editable `/forms/d/<id>` URLs and raw IDs are accepted; `forms.gle` and published `/d/e/` links are rejected. Paid, released final responses and complete question mappings are required. Copy and download must be compared with the stored script at live acceptance.

## 17. REAL Google Form execution result

**NOT RUN — no disposable Form URL or authorized Google session provided. Zero Google responses were submitted.** No claim of general Google Forms compatibility is made.

Use a separate test with 5–10 known, disposable responses recorded on test questionnaires; the 2×4 grouping job has only two responses. Keep the questionnaire/Form clearly identified as a disposable acceptance test. Do not reclassify generated Bot Lab records as human responses to bypass the synthetic-submission block. The owner must execute and authorize `previewMapping()`, `startSubmission()`, `continueSubmission()` and `submissionStatus()` in Apps Script.

Record the initial/final response counts, each mapped title and actual item type, expected versus received values and any errors. Test text, multiple choice, checkbox, and scale individually. Continue the same completed script again and verify no additional responses. Preserve the same project/dataset for resume testing; a separate project has separate state.

Generator branches also exist for paragraph, list, rating, date/date-time, time/duration, grid and checkbox-grid. **Every type remains externally unvalidated.** Branch existence is not proof of correct Google behavior. File-upload question submission has no supported branch. Complex grids, branching, collected-email settings, validation constraints, date/time zones and choice mismatches require explicit testing and must not be advertised as generally supported.

## 18. Synthetic order result

**Live synthetic service: NOT RUN.** Local order tests cover separate blank-template input, requested synthetic count, internal generation, corrections, paid release and labelled CSV. Required live job: one small blank questionnaire, 10 requested responses, payment claim/staff verification, schema inspection, internal generator, inspection/correction of all 10 rows, attached BotRun, READY, and customer download.

All results must remain visibly marked **SYNTHETIC TEST DATA**. Public synthetic Google submission remains blocked. No workaround was added and no synthetic records were passed through the digitization service.

## 19. Notification result

**Live notifications: NOT RUN.** Earlier tests cover events, ownership and the browser notification path. Verify actual unread count, payment verification, processing, needs-attention, payment rejection and READY events under the customer account, then mark read and confirm User B cannot retrieve those records. Database notifications do not establish email delivery.

## 20. Persistence/redeploy result

**NOT RUN. No persistence claim is accepted.** There is no deployed object or row to compare across a restart. Required sequence: record order/document/output IDs and source hashes; wait for work to finish; restart/redeploy API and worker; compare PostgreSQL records, source hashes through both services, owner download and generated output retrieval. Verify object privacy again. Any missing promised source or result fails acceptance.

Only the model cache and temporary OCR files may disappear safely. Customer sources must remain in the shared bucket. Free Render web filesystems are ephemeral; free PostgreSQL expires; free Key Value does not persist data. These do not provide a durable customer-data deployment. [Render free-service limitations](https://render.com/docs/free).

## 21. Cross-user security result

**Live security: NOT RUN.** Prior ownership regressions passed locally. Create two ordinary customers plus a separate staff operator on Render. Attempt known-ID/reference access across orders, questionnaire/schema, documents/source files, answers, page movement, exports, scripts, synthetic results and notifications. Expect denied/not-found with no bytes or mutation; verify the underlying records remain unchanged. Also attempt customer self-verification of payment. Staff access is explicitly authorized, not evidence that ordinary customer isolation failed.

## 22. Observed resource limitations

No Render memory, CPU, OCR duration, retries, timeouts or restarts were observed. The `2c-4g` worker is a starting configuration for measurement, not a certified minimum or batch-capacity estimate. Model downloads/cache initialization may delay first processing. The worker shutdown grace is 300 seconds while task limits are 540 seconds soft/600 hard; drain work before planned redeploy. Unexpected termination may leave a processing job needing operator recovery.

Locally, approximately 2.9 GB disk space remained and the host was under substantial memory pressure. A new full Paddle worker image build was not attempted under those constraints. Existing unrelated containers were left untouched. No ScanToForms containers were running at inspection. No 480-page real OCR workload has been established; the 480-page result is a model/grouping test only.

## 23. Failures discovered

- The original Render blueprint selected manual mode and had no broker/worker, so it could not satisfy the newly required deployed real-OCR path.
- The previous worker instructions required selecting a named Docker target without supplying a Render selection mechanism. The default final image was the API, which lacks Paddle dependencies.
- Render account access, shared bucket credentials, production database URL, SMTP/business configuration and a disposable Google Form are missing from this workspace. This blocks live execution, rather than constituting a reproduced deployed product failure.
- The existing Playwright harness launches local services and manual transcription. Running it unchanged would not be Render acceptance.
- At inspection, remote `main` was still the pre-refactor application, not the tested two-service MVP. Deploying that revision would test the wrong product.
- Local `docker build --check` could not run: the installed CLI lacks Buildx and rejects `--check`. This is recorded as unavailable, not passing. The ordinary base-stage build did pass.
- No deployed application failure was reproduced because no deployed application was accessible.

## 24. Fixes made and validation

Deployment-only changes:

1. `render.yaml`: real Celery mode, eager tasks disabled, private persistent Key Value, separate single-concurrency OCR worker, shared database/storage references. The API Dockerfile and frontend build/start commands remain unchanged.
2. `backend/Dockerfile`: non-secret `RENDER_TARGET` selector reuses existing production/OCR stages; default API selection and explicit local Compose targets remain available.
3. `docs/RENDER_TEST_DEPLOYMENT.md`: exact environment checklist, real-worker setup, private storage verification, persistence procedure, Google test rules and limitations.
4. This report: evidence, unexecuted tests and acceptance blockers.

No models, migrations, business logic, UI, product scope or credentials were changed. No resources were deployed, no database reset, and no external response submission occurred.

| Check this session | Result |
| --- | --- |
| Original and updated `render.yaml` against Render's published JSON schema | PASS locally; not account-side provisioning validation |
| Docker Compose configuration | PASS |
| Blueprint cross-service environment references and real queue/private storage settings | PASS configuration checks |
| Main Dockerfile shared base-stage build | PASS using cached dependencies |
| `git diff --check` | PASS |
| Full new OCR worker image build/runtime | NOT RUN; local resources insufficient for a responsible heavy build |
| Buildx `--check` | UNAVAILABLE; unsupported by installed CLI |
| Live deployment and acceptance tests | NOT RUN; external access/configuration missing |

Previous validation remains documented in [MVP_IMPLEMENTATION_REPORT.md](MVP_IMPLEMENTATION_REPORT.md#20-validation-results): 79 backend tests on each of SQLite and PostgreSQL 16, browser MVP journey, Django/migrations/Ruff/ESLint/TypeScript/build/audit, real printed-text OCR smoke tests, and API image/runtime checks. Those were not rerun as a substitute for external acceptance and do not validate the new Render worker runtime.

## 25. Remaining blockers

1. Connect Render and identify the intended workspace/project and affordable API/worker/queue resources. Confirm the remote source commit can be deployed.
2. Supply a persistent PostgreSQL database and private shared S3 bucket, with usable least-privilege credentials in Render. Verify actual privacy and persistence.
3. Configure bank details, positive service rates, exact deployment origins/API URL and working SMTP with an inbox for delivery checks.
4. Build/deploy the actual worker and services, then complete real queued OCR and every deployment/security/persistence acceptance step.
5. Supply an owner-accessible disposable Google Form and complete its manual authorization/execution and response-by-response comparison.

Until those are resolved, the answer to “does the complete product work outside the test suite?” is **not yet established**.

## Capability matrix

“Prior pass” refers to the previous local validation, not a fresh test or a production certification. No live rows are silently treated as passing.

| Capability | Local | Render | Real External Test | Verdict |
| --- | --- | --- | --- | --- |
| Landing page | Prior build/browser pass | NOT RUN | Not observed | Pending live acceptance |
| Registration | Prior backend/browser pass | NOT RUN | Email not delivered/tested | Blocked |
| Login | Prior backend/browser pass | NOT RUN | Not observed | Pending |
| Password reset | Prior backend pass | NOT RUN | SMTP/reset link not tested | Blocked |
| Order creation | Prior backend/browser pass | NOT RUN | Not observed | Pending |
| Manual payment | Prior backend/browser pass | NOT RUN | No transfer/reconciliation | Pending |
| Digitization upload | Prior backend/browser pass | NOT RUN | Real private bucket untested | Blocked |
| OCR | Prior one-page real engine smoke | NOT RUN | Deployed queue/worker untested | Blocked |
| Page grouping | Prior regressions; 480-page model | NOT RUN | No real deployed 8-page run | Pending |
| Review | Prior backend/browser pass | NOT RUN | No real deployed correction | Pending |
| CSV | Prior backend pass | NOT RUN | No deployed download | Pending |
| XLSX | Prior backend/browser pass | NOT RUN | No deployed download | Pending |
| Apps Script generation | Prior backend/browser pass | NOT RUN | No deployed generation | Pending |
| Google submission | Generator code/tests only | NOT RUN | NOT RUN | Not accepted |
| Synthetic order | Prior backend tests | NOT RUN | No deployed operator fulfillment | Pending |
| Notifications | Prior backend/browser pass | NOT RUN | Not observed | Pending |
| File persistence | Storage code inspected | NOT RUN | No real bucket/redeploy test | Blocked |
| Cross-user isolation | Prior regression pass | NOT RUN | Deployed endpoints/bucket untested | Pending |

## Readiness answers

1. **Is Render suitable for the current controlled beta?** A plausible deployment target with a paid worker/API/queue, PostgreSQL and private shared object storage. Suitability has not been demonstrated by a live run. An entirely free setup does not meet this acceptance architecture.
2. **Can we invite 3–5 test students?** Not on the evidence available here. First deploy and pass authentication, privacy, persistence and both small service journeys; invite a controlled group only after those gates pass.
3. **Can we safely accept money yet?** Not established. Do not open paid intake before reliable delivery, payment reconciliation, recovery and the promised Google workflow are actually verified. A clearly agreed test transfer is not a public commercial launch.
4. **Has a real Google Form been successfully populated?** No evidence of that; zero submissions were made in this task.
5. **Which questionnaire types are safe to advertise?** No type is live-certified yet. The narrow candidate offer is operator-reviewed digitization of clear printed questionnaires supplied in respondent/page order, with manually verified final values. Advertise no OCR accuracy percentage or guaranteed Google compatibility.
6. **Which types must remain beta/unsupported?** Handwriting and ambiguous checkbox/tick/circle/Likert recognition remain unmeasured; shuffled respondent identification, combined multi-respondent PDFs, Google file-upload submission and public synthetic Google submission are unsupported in this scope. Grids, dates/times, ratings, branching and special Google constraints remain externally unvalidated.
7. **Maximum batch size actually tested?** Render: zero pages. Previous real local OCR smoke: one printed page per engine. Local model/grouping regression: 480 pages representing 120 respondents, not real 480-page OCR. The requested live 8-page test has not run.
8. **What infrastructure must change before scaling?** First establish the worker, persistent queue/database/private storage and measure the small live workload. Then size resources from observed peak memory/latency, test interrupted-job recovery and backups/restores, and establish operator capacity. Do not extrapolate from an 8-page test.
9. **Remaining first paid pilot blockers?** External access/configuration, real deployed OCR and result delivery, password recovery, private persistent uploads, cross-user acceptance, actual bank reconciliation, and successful disposable Google execution for the advertised types.
10. **Remaining broader launch blockers?** All pilot gates plus representative recognition/Google compatibility evidence, measured sustained capacity, operator/support processes, monitoring, failure recovery and tested backup/restore. Passing the local suite alone is insufficient.
