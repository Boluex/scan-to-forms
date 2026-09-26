# Private shared object storage (Cloudflare R2)

Status: **application support implemented; real R2 acceptance REQUIRES OWNER ACTION**. No account, bucket, credentials or paid service has been provisioned. The Render blueprint still deploys no persistent storage or worker. Keep its upload-loss and OCR-unavailable notices until each corresponding live test passes.

## Owner setup

1. Create/sign in to your Cloudflare account. Review R2 billing terms before enabling it. R2 includes usage allowances; those are not a hard spending cap or a guarantee of $0. The owner must approve any account/billing setup. See [R2 activation](https://developers.cloudflare.com/r2/get-started/) and [current pricing](https://developers.cloudflare.com/r2/pricing/).
2. Open **Storage & databases → R2 → Overview** and enable R2 if necessary.
3. Create a dedicated beta bucket. Leave both the public `r2.dev` endpoint and public custom domains disabled. Do not publish object links. Verify these controls in the bucket settings; an application setting alone cannot make an already-public bucket private. See [public access controls](https://developers.cloudflare.com/r2/buckets/public-buckets/).
4. Create R2 S3 API credentials with **Object Read & Write** permission scoped to this bucket. The worker and API need upload/read/delete access for normal operation and cleanup. Use separate scoped tokens if desired; they must address the same bucket. Save the access key and secret securely. These are S3 credentials, not a Cloudflare bearer token. See [R2 tokens](https://developers.cloudflare.com/r2/api/tokens/).
5. Copy the bucket's S3 API endpoint from Cloudflare. Use that HTTPS endpoint, not a public domain. R2 uses region `auto`; this implementation uses standard S3 operations and does not call AWS ACL-management APIs. See [S3 compatibility](https://developers.cloudflare.com/r2/api/s3/api/).
6. Enter the following directly into **Render API environment/secrets**, never chat or source control:

   | Variable | Setting |
   | --- | --- |
   | `OBJECT_STORAGE_ENABLED` | `true` |
   | `AWS_ACCESS_KEY_ID` | Scoped S3 access key |
   | `AWS_SECRET_ACCESS_KEY` | Scoped S3 secret |
   | `AWS_STORAGE_BUCKET_NAME` | Exact private bucket name |
   | `AWS_S3_ENDPOINT_URL` | Exact HTTPS S3 endpoint |
   | `AWS_S3_REGION_NAME` | `auto` for R2 |
   | `AWS_S3_ADDRESSING_STYLE` | `path` |

   `OBJECT_STORAGE_ENABLED` takes precedence over the retained `USE_S3_STORAGE` alias. Do not put any storage credentials in frontend or `NEXT_PUBLIC_*` variables. Static files continue to use WhiteNoise, independently of source-file storage.
7. Copy `.env.worker.example` to `.env.worker` on Ubuntu, restrict it to mode 600, and enter the same storage configuration plus the external database/broker URLs described in [the worker guide](REMOTE_OCR_WORKER.md). Apply the new Django migration to the API database before starting this revision of the worker. Deploy matching API and worker commits.
8. Never commit `.env.worker` or another real `.env` file. They are ignored. Do not log settings, connection URLs, credentials, or customer source contents.
9. Upload one **disposable** PNG/JPG/PDF through an authenticated test order. Check that its database key and private bucket object exist. New keys include owner/order/document UUIDs and a random basename; original filenames remain metadata. The API exposes authenticated download routes, not object URLs.
10. Preview as the owner and as an explicitly authorized staff operator. Test another customer, an anonymous request, the document/page UUID routes and a known object key: they must not reveal the source. Confirm anonymous bucket access is denied. The browser streams through the authenticated API, so bucket browser CORS is unnecessary. Responses use `Cache-Control: private, no-store`.
11. Start the Ubuntu worker and perform the paid 2-respondent × 4-page acceptance job in the worker guide. The worker must retrieve the same objects and write real OCR results into the same PostgreSQL database. A storage smoke test alone does not establish this queue/payment path.
12. Record hashes of test source files, redeploy the API, restart the worker, and re-download through authorized API routes. Compare bytes, inspect database state/results, and confirm the worker can still read the source. Only after this passes may the disposable-upload warning be revised. Keep the OCR-unavailable warning until the real remote worker job passes too. Rebuild the frontend when changing its public notice.

## Existing files and deletion

Enabling object storage does **not** move existing `MEDIA_ROOT` files. Database file keys are preserved. Before switching a deployment containing files worth keeping, copy those objects to the bucket under exactly their existing keys and verify contents privately. For disposable beta data, retain local originals and use the existing permitted re-upload workflow. Do not reset the database or silently discard files.

Model deletion records a durable `StorageDeletion` intent inside the database transaction. After commit it attempts object deletion. Queryset/cascade deletion uses this same path; rollback leaves the file intact. Order deletion protections remain unchanged. A storage outage leaves a retryable intent visible to staff in Django Admin. On a machine with the matching database/storage environment, run:

```bash
python manage.py cleanup_source_files --limit 100
```

Repeat until pending failures are resolved; inspect error codes rather than assuming deletion succeeded. This command does not require Redis. Intents are bound to a non-secret storage identity, and refuse deletion after a backend/bucket change or while a document still references the key. Restore the correct configuration to retry old intents. With local filesystem storage, run cleanup on the host that actually holds those files.

Database and object-store writes cannot commit atomically: a process dying after an upload but before its database save may still leave an orphan. This change does not add a blanket bucket sweep or a retention policy. Do not enable a bucket lifecycle rule that unexpectedly deletes active questionnaires. Backups, account access and retention remain operator responsibilities.

## Local filesystem mode

`OBJECT_STORAGE_ENABLED=false` retains normal `MEDIA_ROOT` development storage and Docker Compose behavior. A remote Ubuntu worker cannot read Render's ephemeral local files; object storage is required for that topology. No bucket has been made mandatory for local developers.

OCR temporarily streams the private source into a mode-600 local file, then deletes its temporary directory on normal success or Python exceptions. No permanent worker upload copy is retained. A forced process kill or machine crash can leave temporary files; protect the worker disk and remove stale `scanforms-ocr-*` directories only after confirming no worker is using them. The S3 backend spools downloads to disk beyond 1 MiB; OCR itself and PDF rendering still need memory and temporary disk space.
