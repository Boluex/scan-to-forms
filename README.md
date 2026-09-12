# ScanToForms

ScanToForms turns completed paper questionnaires into reviewed, structured responses. Users upload PDF or image questionnaires, local OCR extracts the content, uncertain answers are corrected in a human-review interface, and confirmed data can be exported to CSV/XLSX or submitted to Google Forms with generated Apps Script.

Survey-reward campaigns and respondent monetization are not part of this product.

## What is implemented

- Django REST API, PostgreSQL, Redis and Celery
- Next.js/TypeScript frontend
- Email/password authentication, verification/reset flows, roles and audit logs
- Secure PDF/JPG/JPEG/PNG uploads with ownership, signature, size and page validation
- OpenCV perspective correction, deskewing, denoising and contrast enhancement
- PaddleOCR 3.x as the primary image OCR engine
- Tesseract fallback and embedded-PDF text extraction
- Relational questionnaire/version/question/response/answer schema
- Multi-page respondent grouping for PDF-per-respondent, manual-page and ordered bulk-image uploads
- Missing, duplicate, out-of-order and low-confidence page validation with manual page reassignment
- Human review with confidence values
- CSV export for all users and paid-plan XLSX enforcement
- Monthly OCR limits and extra-page credits
- Paystack checkout, server verification, signed webhooks and recurring subscription events
- Bot Lab synthetic-data generation with hard synthetic labels
- Google Forms Apps Script generation for confirmed human batches and completed Bot Lab runs

## Pricing configured in the application

| Plan | Monthly | Yearly | OCR pages/month | Bot Lab runs/month |
| --- | ---: | ---: | ---: | ---: |
| Free | ₦0 | — | 10 | 0 |
| Student Pro | ₦3,500 | ₦35,000 | 30 | 1 |
| Researcher Pro | ₦5,000 | ₦50,000 | 35 | 2 |
| Organization | From ₦15,000 | From ₦150,000 | 100 pooled | 5 |

Organization workspaces support at most 10 people. Extra OCR costs ₦1,500 per 100 pages. See [docs/PRICING.md](docs/PRICING.md) for all entitlements.

## What you need before starting

- Docker with Docker Compose, or Python 3.13 plus Node.js 20+
- A Paystack account for payment testing
- A public HTTPS URL before testing Paystack webhooks
- A Google account with edit access to every Google Form you want to populate
- Sufficient disk space for PaddlePaddle, PaddleOCR dependencies and downloaded OCR models

The application does not need paid OCR or LLM API keys.

## Multi-page questionnaire responses

The application distinguishes physical pages from logical respondent responses. For a 46-question questionnaire with four pages and 50 respondents:

```text
200 uploaded physical pages -> 50 logical Responses -> 50 export rows -> 50 Google Forms records
```

The hierarchy is `Questionnaire -> QuestionnaireVersion -> ResponseBatch -> Response -> DocumentPage -> Answer`. `DocumentPage` is the response-page record: it keeps source/upload order separately from its assigned questionnaire page number. OCR usage is charged per physical page, while exports and Apps Script work per logical `Response`.

The digitizer supports:

- one multi-page PDF per respondent;
- explicit page slots for a manually created respondent;
- ordered bulk images grouped by `QuestionnaireVersion.expected_page_count`.

Bulk image order is only a provisional assignment. OCR-neutral grouping happens before OCR; after page OCR, deterministic page markers and template-text similarity can refine the assignment. Uncertain pages remain visibly flagged and must be corrected in review. The product does not claim a trained or universally accurate automatic page classifier.

See [docs/MULTI_PAGE_GROUPING.md](docs/MULTI_PAGE_GROUPING.md) for the domain model, API workflow, validation states and current limitations.

## Fastest local start: Docker

Create the environment file:

```bash
cp .env.example .env
```

Build and run PostgreSQL, Redis, Django, the PaddleOCR worker and Next.js:

```bash
docker compose up --build
```

Open:

- Frontend: <http://localhost:3000>
- Django API documentation: <http://localhost:8000/api/docs/>
- Django admin: <http://localhost:8000/admin/>

Create an administrator:

```bash
docker compose run --rm api python manage.py createsuperuser
```

The OCR worker image is intentionally much larger than the API image because it contains PaddlePaddle and document-processing dependencies.

## Local development without Docker

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements/dev.txt
pip install -r backend/requirements/ocr.txt
```

For a lightweight SQLite development session:

```bash
export DATABASE_URL=sqlite:///db.sqlite3
export CELERY_TASK_ALWAYS_EAGER=true
python backend/manage.py migrate
python backend/manage.py runserver
```

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

For normal PostgreSQL/Redis/Celery development, use Docker Compose or configure `DATABASE_URL` and `REDIS_URL`, then start a worker:

```bash
cd backend
celery -A config worker -l info
```

## PaddleOCR setup and verification

The OCR dependency file installs PaddleOCR, PaddlePaddle and OpenCV. PaddleOCR requires PaddlePaddle 3 or later; see the [official PaddleOCR installation guide](https://paddlepaddle.github.io/PaddleOCR/main/en/quick_start.html).

Verify imports and versions:

```bash
PADDLE_PDX_CACHE_HOME=.cache/paddlex .venv/bin/python -c "import cv2, paddle, paddleocr; print('OpenCV', cv2.__version__); print('Paddle', paddle.__version__); print('PaddleOCR', paddleocr.__version__)"
```

Then run an end-to-end OCR smoke test. The first Paddle run can take several minutes while models download:

```bash
cd backend
PADDLE_PDX_CACHE_HOME=../.cache/paddlex ../.venv/bin/python manage.py ocr_smoke_test --engine paddleocr
```

The first real PaddleOCR run downloads the selected OCR models. Warm the worker while it has network access before deploying into a restricted production network. Keep the model cache on persistent storage in production; otherwise a new worker may download models after every replacement.

OCR environment settings:

```dotenv
OCR_ENGINE=auto
PADDLEOCR_LANG=en
PADDLEOCR_DEVICE=cpu
PADDLE_PDX_CACHE_HOME=.cache/paddlex
```

- `auto`: try PaddleOCR, then fall back to Tesseract.
- `paddleocr`: require PaddleOCR and fail visibly if it cannot run.
- `tesseract`: deliberately use Tesseract.

For production, use `OCR_ENGINE=paddleocr` after the benchmark dataset passes. This prevents an unnoticed fallback from changing extraction quality.

## Paystack test setup — actions you must complete

Payment code is implemented, but the repository cannot create or obtain your Paystack account credentials. Complete these steps yourself.

### 1. Create the Paystack account

Create or sign in to Paystack, remain in **Test Mode**, then open **Settings → API Keys & Webhooks**. Paystack test keys start with `pk_test_` and `sk_test_`; live keys start with `pk_live_` and `sk_live_`. Read [Paystack's API-key guide](https://paystack.com/docs/api/authentication/).

### 2. Put test keys in `.env`

```dotenv
PAYSTACK_PUBLIC_KEY=pk_test_replace_me
PAYSTACK_SECRET_KEY=sk_test_replace_me
```

The secret key belongs only on the Django server. Never put it in frontend code, screenshots, chat messages or Git. `.env` is ignored by Git; `.env.example` contains names only.

### 3. Create six recurring plans in Paystack Test Mode

Open **Plans → New Plan** and create the following exact plans. Do not add commas to API amounts; Paystack stores amounts in kobo internally.

| Paystack plan | Amount | Interval | Environment variable |
| --- | ---: | --- | --- |
| ScanToForms Student Pro Monthly | ₦3,500 | Monthly | `PAYSTACK_STUDENT_MONTHLY_PLAN_CODE` |
| ScanToForms Student Pro Yearly | ₦35,000 | Annually | `PAYSTACK_STUDENT_YEARLY_PLAN_CODE` |
| ScanToForms Researcher Pro Monthly | ₦5,000 | Monthly | `PAYSTACK_RESEARCHER_MONTHLY_PLAN_CODE` |
| ScanToForms Researcher Pro Yearly | ₦50,000 | Annually | `PAYSTACK_RESEARCHER_YEARLY_PLAN_CODE` |
| ScanToForms Organization Monthly | ₦15,000 | Monthly | `PAYSTACK_ORGANIZATION_MONTHLY_PLAN_CODE` |
| ScanToForms Organization Yearly | ₦150,000 | Annually | `PAYSTACK_ORGANIZATION_YEARLY_PLAN_CODE` |

Copy each generated `PLN_...` code into `.env`:

```dotenv
PAYSTACK_STUDENT_MONTHLY_PLAN_CODE=PLN_replace_me
PAYSTACK_STUDENT_YEARLY_PLAN_CODE=PLN_replace_me
PAYSTACK_RESEARCHER_MONTHLY_PLAN_CODE=PLN_replace_me
PAYSTACK_RESEARCHER_YEARLY_PLAN_CODE=PLN_replace_me
PAYSTACK_ORGANIZATION_MONTHLY_PLAN_CODE=PLN_replace_me
PAYSTACK_ORGANIZATION_YEARLY_PLAN_CODE=PLN_replace_me
```

Paystack documents plan creation and automatic subscription charging in its [Subscriptions guide](https://paystack.com/docs/payments/subscriptions/). If a plan code is absent, ScanToForms can accept a one-period payment, but automatic renewal will not be established. Configure all six codes before public testing.

### 4. Configure callback and webhook URLs

Set the browser return URL in `.env`:

```dotenv
FRONTEND_URL=https://staging.example.com
PAYSTACK_CALLBACK_URL=https://staging.example.com/dashboard/billing/callback
```

In Paystack **API Keys & Webhooks**, set the webhook URL to:

```text
https://api-staging.example.com/api/v1/billing/paystack/webhook/
```

The webhook must be publicly reachable over HTTPS; Paystack cannot call `localhost`. The backend validates the `x-paystack-signature` HMAC-SHA512 signature before processing an event. See [Paystack's webhook guide](https://paystack.com/docs/payments/webhooks/).

For local webhook work, use a trusted HTTPS tunnel and put its temporary API URL in the Paystack Test Mode webhook setting. Do not reuse a development tunnel URL in Live Mode.

### 5. Run a complete test payment

1. Restart Django after changing `.env`.
2. Register and verify a test user.
3. Open **Plans & billing**.
4. Purchase Student Pro using a card from [Paystack's official test-payment page](https://paystack.com/docs/payments/test-payments/). Never use a real card in Test Mode.
5. Confirm the callback page reports a verified payment.
6. Confirm Django admin shows a successful `PaymentTransaction` and active `Subscription`.
7. Confirm the Paystack dashboard shows `charge.success` and `subscription.create` activity.
8. Test the ₦1,500 extra-page purchase separately.
9. Send a wrong/failed test payment and verify no subscription or OCR credit is granted.

### 6. Before changing to live keys

- Activate and verify the Paystack business account.
- Recreate all six plans in **Live Mode** and replace every test `PLN_...` code with its live equivalent.
- Replace both test keys with live keys in the production secret manager.
- Set the production callback and webhook HTTPS URLs.
- Make one low-value real transaction and reconcile the Paystack record, webhook, local transaction and subscription.
- Rotate any key that has been exposed.

## Google Forms Apps Script workflow

No Google Cloud OAuth credentials are required for the current workflow. The user runs the generated code inside Google Apps Script and authorizes access directly with Google.

### Preparing the form

1. Create the target Google Form.
2. Make every mapped item title unique.
3. Ensure choices, checkbox options, scales and grids match the questionnaire values exactly.
4. Copy the Form ID from its edit URL: `https://docs.google.com/forms/d/FORM_ID/edit`.
5. Confirm the Google account that will run the script can edit the form.

### Generating and running the script

1. Confirm human responses in ScanToForms, or complete a Bot Lab run.
2. Open **Google Forms** in the dashboard.
3. Choose the confirmed batch or synthetic Bot Lab dataset.
4. Enter the Form ID/edit URL and review every title mapping.
5. Generate and copy/download the `.gs` script.
6. Open <https://script.google.com>, create a project, paste the script and save.
7. Run `previewMapping()` first and inspect the execution log.
8. Authorize Forms access when Google prompts. Apps Script requires the user at the keyboard to authorize private Google services; see [Google's authorization guide](https://developers.google.com/apps-script/guides/services/authorization).
9. Run `startSubmission()` only after the preview is correct.
10. The script processes at most 40 records per execution. Run `continueSubmission()` until `submissionStatus()` reports complete.

The script uses `FormApp.openById()`, `form.createResponse()`, `withItemResponse()` and `submit()` as documented by [Google FormApp](https://developers.google.com/apps-script/reference/forms/form-app) and [FormResponse](https://developers.google.com/apps-script/reference/forms/form-response).

The generated script stores submitted ScanToForms response IDs in Google Script Properties to reduce accidental duplicates during normal reruns. Do not delete those properties or create a second Apps Script project for the same generated dataset unless duplicate submissions are intentional.

Synthetic scripts and exports are permanently labeled:

```text
SYNTHETIC DATA — NOT HUMAN RESEARCH RESPONSES
```

Never present Bot Lab output as genuine research participation.

## Important environment variables

Start from `.env.example`. Important production values include:

```dotenv
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=api.example.com
DJANGO_CORS_ALLOWED_ORIGINS=https://app.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://app.example.com
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
MEDIA_ROOT=/app/media
OCR_ENGINE=paddleocr
PADDLEOCR_LANG=en
PADDLEOCR_DEVICE=cpu
PADDLE_PDX_CACHE_HOME=/models/paddlex
FRONTEND_URL=https://app.example.com
NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
PAYSTACK_SECRET_KEY=sk_live_replace_me
PAYSTACK_PUBLIC_KEY=pk_live_replace_me
ADMIN_CONTACT_EMAIL=admin@example.com
```

Use object storage rather than an ephemeral container filesystem for uploaded documents in production.

## Validation commands

Backend:

```bash
source .venv/bin/activate
cd backend
pytest -q
ruff check apps config tests
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py check --deploy
```

Frontend:

```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

## Production checklist

- `DEBUG=False`
- Strong `DJANGO_SECRET_KEY`
- HTTPS, secure cookies, HSTS, allowed hosts, restricted CORS and trusted CSRF origins
- PostgreSQL and Redis on private networking
- Persistent private object storage for uploads
- Isolated OCR workers with CPU, memory and execution limits
- Paddle models warmed and cached before serving users
- Malware scanning for uploaded files where available
- Paystack live keys stored in a secret manager
- Correct Live Mode plan codes, callback URL and signed webhook URL
- Backups plus a tested restore procedure
- Representative OCR benchmark dataset and accuracy thresholds
- Logs/alerts for failed OCR, failed payments and webhook errors
- Privacy policy, retention policy and user-controlled deletion

## Current limitations

- OCR accuracy still needs benchmarking on representative printed, photographed, marked and handwritten questionnaires.
- Automatic page classification currently uses explicit `Page X of Y` text and deterministic template-text similarity. Files without reliable markers/template text retain provisional order and require human verification.
- Individual pages inside one uploaded PDF can be renumbered but cannot be moved independently to another respondent; upload separate images when cross-respondent movement is required.
- Handwriting is confidence-based and always requires human review when uncertain.
- Google Form structure is mapped by exact item title because direct Google OAuth/Form API synchronization is not implemented yet.
- Apps Script cannot bypass Google account permissions or Apps Script quotas.
- Advanced analytics, priority Celery routing and self-service organization invitations remain roadmap items.

See [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for product boundaries and system design.
