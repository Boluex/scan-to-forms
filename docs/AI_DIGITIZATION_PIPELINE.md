# OCR and optional AI processing instructions

Status: provider-independent processing specification and reusable prompt pack, 8 October 2026. The application currently runs OCR and heuristic parsing; the LLM/vision stages below are not wired into the worker. Use the prompt pack for supervised trials, not automatic release.

## Accuracy contract

No prompt makes every small or large model accurate. The service obtains reviewed results through source evidence, deterministic checks and administrator approval. Different models can use the same contract while producing different draft quality, speed and review workload. JSON validity, OCR confidence, model agreement and a model's claimed confidence are not proof of factual correctness.

PaddleOCR already uses machine learning for text recognition. An additional language/vision model is optional: it can help organise text into questions and interpret images. A text-only model cannot independently see a faint tick that OCR omitted. Retain manual entry when no suitable model is available or a model fails evaluation.

## Processing stages

| Stage | Input | Output and gate |
| --- | --- | --- |
| 1. Intake | Original photos/PDFs and customer instructions | Private originals, hashes, order/document IDs, expected counts; reject unsupported/corrupt files |
| 2. Page inventory | Every physical page | Provisional printed order and respondent assignment; flag missing/duplicate pages; admin resolves uncertainty |
| 3. Image preparation | Original page | Derived image and preprocessing metadata; preserve original and coordinate transforms |
| 4. Text OCR | Original/derived image | Text, boxes, OCR engine/version and confidence; never reinterpret text confidence as answer confidence |
| 5. Structure extraction | Page image plus OCR and adjacent-page context | Draft questions, options, sections, scale columns and table rows; no respondent answers in the schema |
| 6. Schema review | Draft schema beside original pages | Administrator approves complete wording, order, types and options; freeze schema version |
| 7. Answer extraction | Approved schema, one respondent's page/crops and OCR | One candidate per applicable question with evidence and explicit blank/unclear status |
| 8. Validation | Candidates and approved schema | Type/option/page checks, missing keys, duplicates and conflicts; failed values stay pending |
| 9. Admin review | Source crop beside each candidate | Confirm or correct every field for the initial release; record operator, time, reason and provenance |
| 10. Packaging | Approved schema/responses | Deterministically generated artifacts; release readiness separate from payment |

Keep a whole-page preview and close crops. For a table, include row labels and column headings with each crop: a tick without its headings cannot identify the answer. For perspective-corrected images, boxes must declare the image version/coordinate space; do not draw derived-image boxes on originals without a transformation.

Separate page order from respondent identity. Pages with the same questionnaire layout can belong to different people. Ask for explicit upload grouping or admin confirmation when identity cannot be established. A blank page is not automatically a new template or a missing page.

## Provider adapter contract

Implement provider adapters behind the same two operations:

```text
extract_structure(page_packet, schema_contract) -> draft_structure
extract_answers(approved_schema, respondent_packet, answer_contract) -> draft_answers
```

Each packet contains an order-scoped document ID, source hash, physical and assigned page numbers, original dimensions, image/crop IDs, OCR regions with stable IDs, instructions and relevant continuation context. Each result records provider/model/version or digest, prompt version, request ID, schema version, timing and validation outcome. Never let the model choose tenant IDs, payment status, approval state or output destinations.

Model capabilities determine eligible tasks:

- Text model: candidate structure from OCR text and explicit region IDs; uncertain layout requires review. No image-selection claims.
- Vision model: structure/answer candidates from supplied images or crops. Evidence still needs visual verification.
- Model with structured output: request the schema directly, then independently validate it.
- Model without structured output: request JSON, parse and validate; one bounded repair attempt for formatting only, then manual review. Never silently drop invalid fields.

Use the same downstream validators and review requirements for Ollama and hosted APIs. Timeouts, invalid JSON, truncation, unavailable models or context overflow produce a failed stage/pending review, not an empty successful result. Retry transient failures with bounded attempts and retain previous attempts for audit. Do not retry indefinitely or accept the last answer merely because it differs.

## Output contract

Use strict schemas (`additionalProperties: false`) for the eventual adapter. The following is the required data contract, not an already implemented database/API schema.

Structure fields:

- `schema_version`, `pages_seen`, `sections`, `questions`, `unresolved`.
- Each question: immutable `key`, printed label, exact text, section ID, order, type, source pages, option IDs/labels/order, grid row/column IDs where applicable, required state (`true`, `false` or `null` if not evidenced), continuation relationship, and evidence references.
- Preserve printed question labels; assign an internal unique key only when needed. A repeated printed number must not overwrite an earlier question.
- Record unsupported constructs explicitly: branching, rankings, formulas, uploads/signatures, diagram questions, unclear scales and instructions whose meaning is uncertain. Do not silently convert all of them to short text.

Answer fields:

```json
{
  "question_key": "C2",
  "status": "CANDIDATE",
  "value": 3,
  "evidence": [
    {"page_id": "page-3", "crop_id": "C2-with-headings", "region_ids": []}
  ],
  "issue_codes": [],
  "observations": "A mark appears in the column labelled 3; requires visual review."
}
```

Allowed extraction statuses: `CANDIDATE`, `BLANK`, `UNCLEAR`, `CONFLICT`, `NOT_VISIBLE`. All statuses remain unapproved until a reviewer acts. `BLANK` requires the complete answer area to be visible. For unreadable or absent source areas use `UNCLEAR` or `NOT_VISIBLE`, with `value: null`. Preserve apparent multiple selections on single-choice questions as `CONFLICT`; never select whichever looks most likely. A documented user clarification is `USER_SUPPLIED` provenance handled outside the model.

Stable option/row/column IDs, not array position alone, should represent selections. Preserve text answers as written; store any approved normalisation separately. For grids, include every row and map to the approved column IDs before deterministic export to the app's answer format.

## Reusable instructions

Use [the common instruction](prompts/digitization-common.md) for every call, followed by either [structure extraction](prompts/digitization-structure.md) or [answer extraction](prompts/digitization-answers.md). Supply the strict response schema separately. Do not ask one model call to invent the questionnaire, guess answers and generate executable Apps Script together.

For small models, process a page or small crop group at a time with the relevant section/scale context. Resolve continuations across adjacent pages explicitly. For larger models, additional pages can help but the same evidence and coverage rules apply. Neither model size nor a second model's agreement bypasses admin approval.

## Local Ollama trial setup

Inspection found the Ollama executable on this computer, about 15 GiB total RAM and about 2.7 GiB available at that moment, with swap already in use. That is not evidence that an inference server, a vision model or sufficient GPU memory is ready. Do not choose or download a large model just because the executable exists.

Before a supervised trial:

1. Check available RAM/GPU memory and existing models. Choose a vision-capable model for image tasks and record its exact version/digest. Benchmark it rather than assuming a size fits or guarantees accuracy.
2. Use a loopback-only Ollama endpoint for the local adapter. Do not expose an unauthenticated inference service publicly.
3. Run OCR and model trials sequentially at first. If memory/time limits are exceeded, reduce crop size/context, unload the model, or use manual review. Keep the existing OCR worker responsive.
4. For local `/api/chat`, send the common/task instructions, images, `stream: false`, a strict schema in `format`, and low sampling temperature where supported. The REST image input is base64. The SDK uses a different image input interface; do not interchange request formats.
5. Independently validate returned JSON and the evidence references. Store draft results separately from approved answers.

Ollama documents its [chat request](https://docs.ollama.com/api/chat), [image input](https://docs.ollama.com/capabilities/vision) and [JSON-schema structured output](https://docs.ollama.com/capabilities/structured-outputs). At the time checked, its documentation says Ollama Cloud does not support structured outputs; do not assume that local and cloud endpoints offer identical capabilities. Low temperature helps consistency, not truthfulness.

No new environment variables, adapter or installed model are created by these instructions. When implemented, provider URL, model identifier, capability flags, timeout, concurrency, budget and credential references should be explicit server settings with secrets outside source control.

## Hosted API trial setup

Select a provider/model with the input capabilities needed for that stage. Check its official request format and structured-output support at integration time; do not assume all APIs accept the same payload. Keep API keys on the server. Configure which provider may receive customer documents and disclose that use before external processing. Send only the necessary page/crop and omit unrelated account/payment data. Do not silently fall back from local processing to a remote API.

Set per-order limits on pages, retries, tokens/images and cost. Pin model versions where possible. If the provider changes the model behind an alias, rerun evaluations. Provider responses are draft data; they cannot run code, alter orders or send notifications.

## Deterministic validation and release rules

- Every expected page and question must be accounted for exactly once, with explicit continuations where appropriate. Check numbered-label gaps against the images rather than filling them by invention.
- Verify option membership, allowed selection counts, scale range, grid dimensions, dates/numbers and requiredness against the approved schema. Accept legitimate blanks explicitly; do not fill them with zero, No or Neutral.
- Referenced page/crop/region IDs must exist and belong to the correct order/respondent. Reject stale schema versions and cross-respondent references.
- Compare table row labels and columns independently of selected values. A shifted column can produce a valid but incorrect value.
- OCR/vision disagreement, a crossed-out mark, multiple marks, faint handwriting, missing context and unsupported structure block automatic acceptance.
- Preserve human corrections on retries. New candidates appear as a diff; they do not overwrite approved data silently.
- Generate Google Apps Script from the validated schema using application templates and safe JSON serialization. A model does not author arbitrary executable delivery code.
- Staff approves a result version only after source review and all blocking issues are resolved. Payment determines delivery access, not whether uncertain values become correct.

## Evaluation before enabling a model

Build a private, manually checked benchmark covering clear printed questions, wrapped options, multi-page continuations, Likert tables, checkbox grids, faint/crossed-out marks, handwriting, blank pages, missing pages, shuffled respondents and unsupported layouts. Keep a separate held-out set; do not tune prompts using every test case.

Record question/option recall, exact answer match by question type, blank precision, false-filled blanks, row/column shifts, grouping errors, review workload, runtime and memory/cost. Measure the model draft separately from the corrected final output. Report sample sizes and unresolved items; one successful questionnaire proves very little about other layouts.

The four-page trial is a regression case: 45 numbered questions plus 2 location fields; A9 continues on page 2; A7 and B7 have wrapped labels; C2 is 3; page 4 has 12 unanswered questions. The faint street name came from the owner, so it must not become ground truth for what a model can read from the image. Keep personal answers in the ignored private fixture folder, not committed test data.

Initial policy: administrator checks every released field. A weaker model remains usable as a draft assistant if manual correction is acceptable. Any later reduction in review requires measured performance for a specific document type and model version, with abstention for unfamiliar or uncertain cases. Do not advertise universal accuracy.
