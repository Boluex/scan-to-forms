# Ubuntu terminal workflows

Run these commands from the repository directory. Paths containing spaces must be quoted. Bash launches the existing Python engines; it does not replace PaddleOCR, add an LLM or guess respondent identity.

## 1. Process a customer order already uploaded to the website

The website's sources, grouping and payment record are authoritative. Use its order reference instead of copying its documents into a second untracked job.

```bash
bash scripts/run-order.sh --order STF-000001 --operator YOUR_ADMIN_EMAIL --action status
bash scripts/run-order.sh --order STF-000001 --operator YOUR_ADMIN_EMAIL --action process
```

Replace both placeholders. The operator must be an existing active staff account. Processing requires verified payment, complete uploads and a reviewed schema. With `PROCESSING_MODE=celery`, the command queues work for the Ubuntu worker. It does not launch a second worker or run OCR inside the shell. With manual mode, it opens the existing manual review workflow and does not claim OCR ran.

If needed, provide a reviewed schema before the first processing run:

```bash
bash scripts/run-order.sh --order STF-000001 --operator YOUR_ADMIN_EMAIL \
  --action process --schema "/path/to/reviewed-schema.json"
```

The schema file is an object containing `questions`, in the same format as the admin schema API. Existing reviewed answers cannot be replaced this way. Status is read-only and does not accept a schema file.

For a paid synthetic TEST order with its blank template uploaded:

```bash
bash scripts/run-order.sh --order STF-000002 --operator YOUR_ADMIN_EMAIL --action synthetic
```

The command starts the order if needed and requests the existing synthetic generator. Review its labelled rows in the admin workspace. Payment verification, respondent approval, final script preparation and READY release remain explicit admin actions. The terminal command never marks an order paid/ready automatically.

These commands use `.env.worker` by default. Set `SCANTO_FORMS_ENV_FILE` to another environment file when deliberately targeting staging. The settings determine the database, bucket and queue: check the environment before running a mutation. `SCANFORMS_PYTHON` can select another Python interpreter.

## 2. Digitize a local folder into a private draft

This separate tool does not load `.env`, connect to the application database, enqueue work, notify customers or release results. It calls the OCR engine directly and saves raw extraction plus review drafts. It does not import those drafts into an order automatically.

Use one subfolder per respondent, with explicit page numbers:

```text
questionnaire-batch/
  R-0001/
    page-1.jpg
    page-2.jpg
    page-3.jpg
    page-4.jpg
  R-0002/
    page-1.jpg
    ...
  ...
  R-0070/
    page-1.jpg
    ...
```

Validate all 70 people / 280 physical pages without running OCR:

```bash
bash scripts/digitize-folder.sh "/path/to/questionnaire-batch" \
  --pages-per-respondent 4 --expected-respondents 70 --check
```

Then run PaddleOCR with the reviewed question definitions:

```bash
bash scripts/digitize-folder.sh "/path/to/questionnaire-batch" \
  --pages-per-respondent 4 --expected-respondents 70 \
  --schema "/path/to/reviewed-schema.json" \
  --output "local-results/batch-70-draft"
```

The output folder must not exist. This protects previous results from overwrite. For one respondent whose pages are directly in the input folder, add `--single-respondent`. Missing pages, duplicate slots, identical source pages assigned more than once and a wrong respondent count are rejected before OCR.

The default `--engine paddleocr` fails if PaddleOCR fails; `--engine auto` permits the existing Tesseract fallback. PDFs with embedded text use the existing PDF text extractor, and the recorded engine identifies that choice. This tool does not interpret handwritten ticks automatically; choice/grid values remain pending review. There is no arbitrary-filename sorting heuristic.

Outputs include `manifest.json`, raw per-document `ocr/*.json`, `draft.json`, `run.json`, and, when a schema was supplied, `responses-draft.csv`. All values remain unapproved. Without `--schema`, the tool saves heuristic structure candidates; those can be incomplete and require manual preparation before answer mapping. A failed run records FAILED and retains completed raw outputs; automatic resume is not implemented. Use a new output directory for a rerun.

## Existing WhatsApp filenames or PDFs: explicit manifest

Do not rename source photographs just to test. Supply a JSON manifest mapping original names to respondent and printed page number:

```json
[
  {"respondent": "R-0001", "page": 1, "file": "photo-front.jpeg"},
  {"respondent": "R-0001", "page": 2, "file": "photo-back.jpeg"},
  {"respondent": "R-0002", "page": 1, "file": "respondent-2.pdf", "source_page": 1},
  {"respondent": "R-0002", "page": 2, "file": "respondent-2.pdf", "source_page": 2}
]
```

All `file` paths are relative to the input folder. PDF source pages are one-based. A file cannot escape the folder through `..` or symlinks.

```bash
bash scripts/digitize-folder.sh "/path/to/images" \
  --manifest "/path/to/manifest.json" --pages-per-respondent 2 \
  --expected-respondents 2 --check
```

Remove `--check` and add `--schema`/`--output` to process that inventory. The previously tested four photos are one respondent; they do not establish the remaining 69 people's answers.

## 3. Generate local synthetic TEST data

Synthetic generation needs the questionnaire's reviewed question types/options, not completed respondent answers. If starting with images of a blank template, run the folder OCR command first, prepare/review its schema, then use that schema here. OCR of images alone is not a trustworthy schema approval.

```bash
bash scripts/synthetic-test-data.sh \
  --schema "/path/to/reviewed-schema.json" --schema-reviewed \
  --count 70 --seed 42 --output "local-results/synthetic-70-test"
```

`--schema-reviewed` explicitly acknowledges schema review for this local operation; it does not approve a website order. The fixed seed makes this deterministic. Outputs are JSON and CSV, each retaining a synthetic TEST classification. Grids use configured rows/columns and scales use their bounds. Unsupported/malformed definitions fail instead of silently emitting invalid rows. The generator creates software test data, not statistically representative research participants.

Both local commands use a database-disabled configuration and private output-directory permissions. The first PaddleOCR run may download its OCR models if they are not cached. Neither local command calls an LLM API or needs Google/Firebase credentials.
