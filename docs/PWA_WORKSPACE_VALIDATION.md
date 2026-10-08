# PWA, workspace and worker validation — 7 October 2026

## Delivered in this checkout

- Minimal formal landing page, desktop sidebar, mobile navigation, order workspace and consistent form styling.
- `/admin`: account search, suspension/reactivation, superuser-controlled operator access, announcement preview/broadcast, audit activity and push-delivery counts. API permissions enforce roles independently of navigation visibility. Account changes and announcements are audited.
- Firebase Google sign-in and explicit linking to existing password accounts. Tokens are verified server-side; inactive/suspended accounts are rejected. Firebase configuration is still required.
- Browser device opt-in/out, private generic lock-screen notifications, persisted inbox and a durable retrying push outbox. Delivery runs independently of OCR. No new email delivery integration.
- Installable manifest, icons, explicit offline fallback and bounded immutable-static-asset caching. No offline editing or caching of customer documents/API responses.
- Ubuntu systemd user services for OCR and optional push sender, plus a credential-safe worker preflight command.
- Firebase credential guide and distributed-worker architecture proposal. No student marketplace, payments ledger or untrusted worker gateway was implemented.

## Observed verification

- `SCANTO_FORMS_ENV_FILE=/dev/null .venv/bin/pytest backend/tests -q -o addopts=''`: **150 passed**. Three upstream Firebase `Message.token` deprecation warnings; this version continues to support registration tokens.
- Frontend TypeScript, ESLint and optimized Next.js build passed.
- Three Playwright scenarios passed: customer upload → payment verification → operator review → delivery/download; admin announcement preview/send/inbox; mobile navigation → offline fallback with private-cache exclusion.
- Final browser spot checks passed for returning to a notification deep link after login, native dialog Escape/focus handling, and the updated offline fallback.
- Visually inspected desktop landing, workspace, admin and 390px mobile workspace. Fixed wrapping in the admin search button.
- Backend system check passed; no missing migrations detected.
- Real PaddleOCR 3.7.0 recognised a generated printed fixture locally.
- Real private R2 storage round trips for generated JPG, PNG and image-only PDF: PaddleOCR extraction and temporary/remote fixture cleanup passed.
- Existing `.env.worker` connected to PostgreSQL, Redis and the private bucket. Applied additive account Firebase-UID and push-device/outbox migrations to that shared database.
- Installed user service `scanforms-ocr`, running with concurrency 1. Observed a targeted Celery ping reply and registration of `apps.documents.tasks.process_document`. Automatic startup is not enabled.

## Remaining activation and acceptance work

- Supply Firebase public web configuration, VAPID public key and server credentials as described in [FIREBASE_SETUP.md](FIREBASE_SETUP.md). Rebuild the frontend and deploy matching API code. Google and live FCM delivery have not been externally tested.
- Start `scanforms-push` only after its credentials are configured. It is installed but inactive. Push permission/browser restrictions and sender downtime can delay/prevent a push; the inbox remains the source of record.
- Granted the owner-designated existing account ADMIN role and staff access in the connected database, recorded an audit event, and verified the saved role. Existing password and superuser status were preserved. No test administrator credentials were added to the connected database. Operator privilege changes remain restricted to superusers.
- The browser tests used disposable local SQLite databases and local storage. Their announcement recipients and payments were fixtures, not real users or real transfers.
- A new paid customer job was not submitted through the live queue as part of setup. The real engine, storage, broker connectivity and task registration were verified separately. Run the documented controlled acceptance order before promising turnaround.
- OCR remains dependent on this computer's power/network and available resources. Inspection showed 16 GB total RAM, roughly 2.8 GB available at that moment, and around 22 GB free disk. No GPU capacity was assumed.
- npm audit still reported eight high-severity findings in existing transitive lint/image/source-map tooling. The newly introduced Firebase gRPC dependency was constrained to a patched version. A clean dependency audit remains separate follow-up work.
- The existing user changes in `docs/ROADMAP.md` were preserved.

## Operating the worker

```bash
systemctl --user is-active scanforms-ocr
systemctl --user stop scanforms-ocr
systemctl --user start scanforms-ocr
# After Firebase configuration:
systemctl --user start scanforms-push
```

`stop` allows a warm shutdown with up to 660 seconds for a task. When services are active they can consume eligible queued jobs and use provider quotas. Neither unit is enabled to start automatically at login.

## UI previews

[Landing](previews/landing.png) · [Workspace](previews/workspace.png) · [Admin](previews/admin.png) · [Mobile](previews/mobile.png). These screenshots use disposable test accounts.
