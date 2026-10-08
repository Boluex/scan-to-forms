# Digitization workflow verification — 8 October 2026

Payment remains before processing. No additional AI provider/model was installed or connected.

## Changes

- Administrator inbox/push-outbox events for complete order submission and payment claims; final customer-ready notifications retain existing review/payment gates.
- New-Form destination in customer order setup. Reviewed schema generates Form questions deterministically; creation and response submission are separate functions. Created items use stored IDs, supporting repeated titles. Existing-Form delivery retains title mapping.
- Customer instructions for creation, edit/respondent links, authorization, preview, submission, progress and failures.
- Local folder OCR and labelled synthetic TEST-data Bash tools, plus a terminal command using the existing paid-order processing services.
- Synthetic grids now use configured row/column dimensions, and scale generation respects configured bounds.
- Corrected workflow documents and added terminal usage. Optional AI prompts remain a future extension.

## Observed checks

- Full backend suite: **178 passed**, with 3 existing Firebase registration-token deprecation warnings.
- After improving new-Form progress storage and numeric-bound validation, **9 affected Form/operator tests passed**.
- Added a real API upload regression: **280 distinct generated images in two batches → 70 respondents with four assigned pages each**. Processing remains unavailable before payment. OCR was not run for those generated batch fixtures; this is a grouping/payment test, not a 70-person OCR benchmark.
- The generated JavaScript executed in Node against a mocked Google runtime: creation does not submit answers; repeated creation reuses its Form; duplicate titles map through item IDs; normal submission reruns skip submitted records; interrupted creation stops for review.
- Ran the new Bash OCR command against all four original questionnaire photos using an explicit page manifest and PaddleOCR. It produced one respondent/four pages and unapproved drafts. The sources were unchanged; no app order was modified.
- Ran the synthetic Bash command for 70 labelled test rows. Separate regression tests verify reproducible seeded output, grid dimensions and scale bounds.
- Django migration check: no missing migrations. Shell syntax and targeted Ruff checks passed.
- Frontend TypeScript, ESLint and optimized Next.js production build passed.
- Added browser coverage for both new/existing Form delivery. This session could not start the Playwright test server: `Operation not permitted`. Current browser cases were **not executed**. Earlier UI checks are recorded separately in [PWA_WORKSPACE_VALIDATION.md](PWA_WORKSPACE_VALIDATION.md).

## External acceptance and limits

- No live Google Form was created/submitted in this session. Verify the delivered script in a disposable Form under its owner's Google account, including actual choice/grid/date behavior and authorization.
- Firebase project credentials and real-device delivery still need activation/testing. Creating an outbox row is not proof that a device received a push.
- The current parser does not automatically read ticked choices/grids reliably. Those answers stay pending admin review. Local OCR results are drafts, not completed customer deliveries.
- New-Form conversion supports the application's existing question types with validated options, scale bounds and grid definitions. Sections/branching and questionnaire-only paid orders remain outside the current data model.
- Normal script reruns are protected by saved state; a crash between an external Google write and its progress save can still leave an untracked Form/response. Inspect Google before retrying after a failure.
- The orders migration adds `create_new_form` with a false default for existing orders. The API startup script applies pending migrations. Restart long-running workers after compatible backend/schema updates; this verification did not restart the production worker.

Private questionnaire outputs remain under ignored `local-results/`; existing changes to `docs/ROADMAP.md` are excluded from this release.
