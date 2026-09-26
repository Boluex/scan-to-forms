"""Private source access. Callers must authorize the document before opening it."""

import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.http import FileResponse


def open_source_file(document):
    return document.file.open("rb")


def source_response(document):
    response = FileResponse(
        open_source_file(document), as_attachment=False,
        filename=document.original_filename, content_type=document.content_type,
    )
    response["Cache-Control"] = "private, no-store"
    return response


@contextmanager
def materialize_source_file(document):
    """Bounded-memory copy, private permissions, cleanup even when OCR raises."""
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}.get(
        document.content_type, Path(document.file.name).suffix.lower()
    )
    if suffix not in {".jpg", ".jpeg", ".png", ".pdf"}:
        raise ValueError("Unsupported source file type.")
    with tempfile.TemporaryDirectory(prefix="scanforms-ocr-") as directory:
        path = Path(directory) / f"source{suffix}"
        with open_source_file(document) as source:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as destination:
                shutil.copyfileobj(source, destination, length=1024 * 1024)
        yield path
