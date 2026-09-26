import tempfile
import uuid
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw, ImageFont

from apps.documents.models import UploadedDocument
from apps.documents.services.ocr import extract_document
from apps.documents.storage import materialize_source_file


class Command(BaseCommand):
    help = "Run a local OCR engine against a generated questionnaire image."

    def add_arguments(self, parser):
        parser.add_argument("--engine", choices=("auto", "paddleocr", "tesseract"), default="auto")
        parser.add_argument("--storage", action="store_true", help="Round-trip generated JPG, PNG and image-only PDF through configured storage; real OCR, no database writes.")

    def handle(self, *args, **options):
        image = Image.new("RGB", (1500, 520), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
        except OSError:
            font = ImageFont.load_default(size=42)
        draw.text((70, 80), "What is your department?", fill="black", font=font)
        draw.text((70, 230), "Computer Science", fill="black", font=font)
        if options["storage"]:
            return self.storage_check(image, options["engine"])
        with tempfile.TemporaryDirectory(prefix="scanforms-ocr-smoke-") as directory:
            path = Path(directory) / "ocr-smoke.png"
            image.save(path)
            try:
                result = extract_document(path, preferred=options["engine"])
            except Exception as exc:
                raise CommandError(f"OCR smoke test failed: {exc}") from exc
        text = "\n".join(page.text for page in result.pages)
        if "department" not in text.lower() or "computer" not in text.lower():
            raise CommandError(f"OCR ran with {result.engine}, but expected text was not recognized. Output: {text!r}")
        self.stdout.write(self.style.SUCCESS(f"OCR engine: {result.engine} ({result.model_version})"))
        self.stdout.write(self.style.SUCCESS("Recognized the generated questionnaire text."))

    def storage_check(self, image, engine):
        prefix = f"diagnostics/{uuid.uuid4()}"
        for format_name, suffix, mime in [("JPEG", "jpg", "image/jpeg"), ("PNG", "png", "image/png"), ("PDF", "pdf", "application/pdf")]:
            data = BytesIO()
            image.save(data, format=format_name)
            document = UploadedDocument(original_filename=f"source.{suffix}", content_type=mime)
            storage = document.file.storage
            name = storage.save(f"{prefix}/source.{suffix}", ContentFile(data.getvalue()))
            document.file.name = name
            try:
                with materialize_source_file(document) as path:
                    output = extract_document(path, preferred=engine)
                if path.exists():
                    raise CommandError("Temporary OCR source was not removed.")
                text = "\n".join(page.text for page in output.pages)
                if "department" not in text.lower() or "computer" not in text.lower():
                    raise CommandError(f"{suffix}: engine did not recognize the known test text.")
                self.stdout.write(f"{suffix}: storage round-trip, real {output.engine}, temporary cleanup PASS")
            finally:
                # Diagnostic data only. Report failure instead of hiding an undeleted object.
                try:
                    storage.delete(name)
                except Exception as exc:
                    raise CommandError(f"Diagnostic object cleanup failed ({type(exc).__name__}); inspect the diagnostics prefix.") from None
