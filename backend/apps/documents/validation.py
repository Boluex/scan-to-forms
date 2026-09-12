import hashlib
from pathlib import Path

from django.conf import settings
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from rest_framework import serializers

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
IMAGE_SIGNATURES = {
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
}


def inspect_upload(upload):
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise serializers.ValidationError("Only PDF, JPG, JPEG, and PNG files are supported.")
    if upload.size <= 0 or upload.size > settings.MAX_UPLOAD_BYTES:
        raise serializers.ValidationError(f"File must be between 1 byte and {settings.MAX_UPLOAD_BYTES} bytes.")

    upload.seek(0)
    header = upload.read(16)
    upload.seek(0)
    try:
        if extension == ".pdf":
            if not header.startswith(b"%PDF-"):
                raise serializers.ValidationError("The file content is not a valid PDF.")
            page_count = len(PdfReader(upload).pages)
            content_type = "application/pdf"
        else:
            if not any(header.startswith(signature) for signature in IMAGE_SIGNATURES[extension]):
                raise serializers.ValidationError("The file signature does not match its image extension.")
            with Image.open(upload) as image:
                image.verify()
            page_count = 1
            content_type = "image/jpeg" if extension in {".jpg", ".jpeg"} else "image/png"
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise serializers.ValidationError("The uploaded document is corrupt or unsupported.") from exc
    finally:
        upload.seek(0)

    if page_count < 1 or page_count > settings.MAX_PDF_PAGES:
        raise serializers.ValidationError(f"Documents may contain at most {settings.MAX_PDF_PAGES} pages.")

    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return {"content_type": content_type, "page_count": page_count, "sha256": digest.hexdigest()}

