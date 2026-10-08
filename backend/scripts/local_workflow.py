"""Entry point for isolated local OCR/synthetic drafts. Does not load .env."""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser(
        "digitize", help="Extract unapproved OCR drafts from assigned pages."
    )
    scan.add_argument("folder")
    scan.add_argument("--manifest")
    scan.add_argument("--single-respondent", action="store_true")
    scan.add_argument("--pages-per-respondent", type=int, required=True)
    scan.add_argument("--expected-respondents", type=int)
    scan.add_argument("--schema")
    scan.add_argument("--engine", choices=["paddleocr", "tesseract", "auto"], default="paddleocr")
    scan.add_argument(
        "--check", action="store_true", help="Validate inventory only; no OCR or output writes."
    )
    scan.add_argument("--output")
    synth = commands.add_parser(
        "synthetic", help="Generate labelled test rows from a reviewed schema."
    )
    synth.add_argument("--schema", required=True)
    synth.add_argument("--schema-reviewed", action="store_true", required=True)
    synth.add_argument("--count", type=int, required=True)
    synth.add_argument("--seed", type=int, default=42)
    synth.add_argument("--output", required=True)
    args = parser.parse_args()
    os.umask(0o077)
    from django.conf import settings

    settings.configure(
        SECRET_KEY="local-draft-only",
        USE_TZ=True,
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            *[
                f"apps.{name}"
                for name in (
                    "core",
                    "accounts",
                    "questionnaires",
                    "documents",
                    "orders",
                    "billing",
                    "exports",
                    "notifications",
                    "googleforms",
                    "botlab",
                )
            ],
        ],
        AUTH_USER_MODEL="accounts.User",
        DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
        MAX_UPLOAD_BYTES=25 * 1024 * 1024,
        MAX_PDF_PAGES=100,
        FIREBASE_PUSH_ENABLED=False,
    )
    import django

    django.setup()
    from apps.documents.services.local_workflow import digitize, inventory, load_schema, synthetic

    try:
        questions = load_schema(args.schema) if args.schema else None
        if args.command == "synthetic":
            target = synthetic(questions, args.output, count=args.count, seed=args.seed)
        else:
            groups = inventory(
                args.folder,
                manifest=args.manifest,
                pages_per_respondent=args.pages_per_respondent,
                expected_respondents=args.expected_respondents,
                single=args.single_respondent,
            )
            print(
                f"Inventory: {len(groups)} respondents, {sum(map(len, groups.values()))} physical pages."
            )
            if args.check:
                return
            if not args.output:
                parser.error("--output is required unless --check is used")
            target = digitize(groups, args.output, questions=questions, engine=args.engine)
        print(f"Saved local drafts: {target}. No app order was changed or released.")
    except Exception as exc:
        parser.exit(1, f"Workflow failed: {exc}\n")


if __name__ == "__main__":
    main()
