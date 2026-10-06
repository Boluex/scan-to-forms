# External-services beta configuration validation

Date: September 28, 2026. Scope: deployment configuration/documentation only for the **ZERO-BUDGET / FREE-TIER CONTROLLED BETA**. No product features, model changes or new migrations. No infrastructure provisioned and no paid deployment performed.

## Passed locally

| Check | Result |
| --- | --- |
| Backend suite on isolated PostgreSQL 16 | **139 tests passed**, including 19 new configuration cases |
| Existing migrations on a fresh PostgreSQL database | Applied successfully |
| `makemigrations --check --dry-run` | No changes detected |
| Django `check` and `check --deploy` | No issues |
| Ruff | Passed |
| Frontend ESLint | Passed |
| TypeScript | Passed |
| Next.js 15.5.24 production build | Passed with existing dynamic routes |
| Blueprint configuration tests | Exactly two Free application web services; no database, Key Value, worker, disk or managed-service references |
| Documentation links and diff whitespace | Passed |

Tests used an isolated local PostgreSQL container; it was removed afterward. Existing databases were untouched. The HTTP test client ran with development redirect settings; separate production Django deployment checks ran with debug disabled and secure defaults.

The new tests parse representative Neon URLs, enforce PostgreSQL verified TLS/direct connections, validate Upstash TLS parameters in both Celery connections, reject insecure/missing external settings, verify private R2 options and locally generated expiring signed URLs, and load API/worker templates with the same dummy external values. Existing ownership and PostgreSQL recovery tests also pass. The template comparison does not prove that an owner's separately entered live secrets match.

## Static export assessment

An isolated copy of the unchanged frontend was built with `output: "export"`. Compilation succeeded, but export failed with:

```text
Page "/orders/[reference]" is missing "generateStaticParams()" so it cannot be used with "output: export" config.
```

Order references and questionnaire/review IDs are created after deployment. Enumerating build-time IDs cannot preserve those new URLs. The original configuration remains unchanged and the normal production build passes. Keep the frontend as a Render Free Web Service; no routing rewrite was made.

## Not tested live

Neon TLS handshake/migrations, Upstash queue delivery and quota usage, actual R2 bucket privacy/persistence, Resend inbox delivery, Render health/CORS, and Render → Ubuntu real OCR all **await actual credentials and live acceptance**. No local configuration test is labelled an external connection test. Provider account plans, usage and billing settings have not been inspected.

Follow [the ordered setup checklist](RENDER_SETUP.md) and then [the acceptance procedure](RENDER_TEST_DEPLOYMENT.md). Historical Render-managed datastore reports are explicitly marked as superseded.
