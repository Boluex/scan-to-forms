import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageDraw, ImageFont

from apps.documents.services.ocr import extract_document


class Command(BaseCommand):
    help = "Run a local OCR engine against a generated questionnaire image."

    def add_arguments(self, parser):
        parser.add_argument("--engine", choices=("auto", "paddleocr", "tesseract"), default="auto")

    def handle(self, *args, **options):
        image = Image.new("RGB", (1500, 520), "white")
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 52)
        except OSError:
            font = ImageFont.load_default(size=42)
        draw.text((70, 80), "What is your department?", fill="black", font=font)
        draw.text((70, 230), "Computer Science", fill="black", font=font)
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
