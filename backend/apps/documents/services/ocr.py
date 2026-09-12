import os
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pypdf import PdfReader


@dataclass
class Region:
    text: str
    confidence: float
    bounding_box: dict


@dataclass
class PageOutput:
    page_number: int
    width: int | None
    height: int | None
    text: str
    confidence: float | None
    regions: list[Region]
    preprocessing: dict

    def raw(self):
        return {"regions": [asdict(region) for region in self.regions]}


@dataclass
class DocumentOutput:
    engine: str
    model_version: str
    pages: list[PageOutput]


def _order_quad(points):
    import numpy as np

    ordered = np.zeros((4, 2), dtype="float32")
    sums = points.sum(axis=1)
    differences = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[sums.argmin()]
    ordered[2] = points[sums.argmax()]
    ordered[1] = points[differences.argmin()]
    ordered[3] = points[differences.argmax()]
    return ordered


def _opencv_normalize(image):
    import cv2
    import numpy as np

    rgb = np.asarray(image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    metadata = {
        "engine": "opencv",
        "grayscale": True,
        "perspective_corrected": False,
        "deskew_angle": 0.0,
        "denoised": True,
        "clahe": True,
    }

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = gray.shape[0] * gray.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:8]:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or cv2.contourArea(polygon) < image_area * 0.4:
            continue
        points = _order_quad(polygon.reshape(4, 2).astype("float32"))
        top_left, top_right, bottom_right, bottom_left = points
        width = int(max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left)))
        height = int(max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left)))
        if width < 100 or height < 100:
            break
        destination = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype="float32")
        transform = cv2.getPerspectiveTransform(points, destination)
        gray = cv2.warpPerspective(gray, transform, (width, height), borderMode=cv2.BORDER_REPLICATE)
        metadata["perspective_corrected"] = True
        break

    denoised = cv2.fastNlMeansDenoising(gray, None, 9, 7, 21)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(denoised)
    threshold = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coordinates = cv2.findNonZero(threshold)
    if coordinates is not None and len(coordinates) > 20:
        raw_angle = cv2.minAreaRect(coordinates)[-1]
        if raw_angle < -45:
            correction = -(90 + raw_angle)
        elif raw_angle > 45:
            correction = 90 - raw_angle
        else:
            correction = -raw_angle
        if 0.25 < abs(correction) < 15:
            center = (enhanced.shape[1] / 2, enhanced.shape[0] / 2)
            matrix = cv2.getRotationMatrix2D(center, correction, 1.0)
            enhanced = cv2.warpAffine(
                enhanced,
                matrix,
                (enhanced.shape[1], enhanced.shape[0]),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE,
            )
            metadata["deskew_angle"] = round(float(correction), 3)
    return Image.fromarray(cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)), metadata


def _normalize_image(source):
    image = source.copy() if isinstance(source, Image.Image) else Image.open(source)
    image = ImageOps.exif_transpose(image).convert("RGB")
    try:
        return _opencv_normalize(image)
    except (ImportError, ModuleNotFoundError):
        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image)
        image = ImageEnhance.Contrast(image).enhance(1.25)
        image = image.filter(ImageFilter.MedianFilter(size=3)).convert("RGB")
        return image, {
            "engine": "pillow",
            "grayscale": True,
            "autocontrast": True,
            "median_filter": 3,
            "perspective_corrected": False,
            "deskew_angle": 0.0,
        }


@lru_cache(maxsize=1)
def _paddle_engine():
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(Path.cwd() / ".cache" / "paddlex"))
    from paddleocr import PaddleOCR

    return PaddleOCR(
        lang=os.getenv("PADDLEOCR_LANG", "en"),
        device=os.getenv("PADDLEOCR_DEVICE", "cpu"),
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=True,
    )


def _paddle_images(images):
    import numpy as np

    engine = _paddle_engine()
    import paddleocr
    pages = []
    for page_number, source in enumerate(images, start=1):
        image, preprocessing = _normalize_image(source)
        predictions = engine.predict(np.asarray(image))
        regions = []
        for prediction in predictions:
            prediction_json = prediction.json
            data = prediction_json.get("res", prediction_json)
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            boxes = data.get("rec_boxes", [])
            for text, score, box in zip(texts, scores, boxes, strict=False):
                regions.append(Region(str(text), float(score), {"points": list(map(float, box))}))
        confidence = sum(region.confidence for region in regions) / len(regions) if regions else None
        pages.append(
            PageOutput(
                page_number,
                image.width,
                image.height,
                "\n".join(region.text for region in regions),
                confidence,
                regions,
                preprocessing,
            )
        )
    return DocumentOutput(
        engine="paddleocr",
        model_version=getattr(paddleocr, "__version__", "runtime-default"),
        pages=pages,
    )


def _tesseract_images(images):
    import pytesseract
    from pytesseract import Output

    pages = []
    for page_number, source in enumerate(images, start=1):
        image, preprocessing = _normalize_image(source)
        data = pytesseract.image_to_data(image, output_type=Output.DICT)
        line_groups = {}
        for index, text in enumerate(data["text"]):
            text = text.strip()
            confidence = float(data["conf"][index])
            if text and confidence >= 0:
                key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
                group = line_groups.setdefault(key, {"words": [], "confidences": [], "boxes": []})
                group["words"].append(text)
                group["confidences"].append(confidence / 100)
                group["boxes"].append(
                    (data["left"][index], data["top"][index], data["width"][index], data["height"][index])
                )
        regions = []
        for group in line_groups.values():
            left = min(box[0] for box in group["boxes"])
            top = min(box[1] for box in group["boxes"])
            right = max(box[0] + box[2] for box in group["boxes"])
            bottom = max(box[1] + box[3] for box in group["boxes"])
            regions.append(
                Region(
                    " ".join(group["words"]),
                    sum(group["confidences"]) / len(group["confidences"]),
                    {"x": left, "y": top, "width": right - left, "height": bottom - top},
                )
            )
        confidence = sum(region.confidence for region in regions) / len(regions) if regions else None
        pages.append(
            PageOutput(
                page_number,
                image.width,
                image.height,
                " ".join(region.text for region in regions),
                confidence,
                regions,
                preprocessing,
            )
        )
    return DocumentOutput(
        engine="tesseract",
        model_version=str(pytesseract.get_tesseract_version()),
        pages=pages,
    )


def _pdf_text(path):
    reader = PdfReader(path)
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        regions = [Region(line, 0.75, {}) for line in lines]
        pages.append(PageOutput(index, None, None, text, 0.75 if text else None, regions, {"embedded_text": True}))
    return DocumentOutput("pypdf", "embedded-text", pages)


def _render_pdf(path):
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    images = []
    try:
        for page in document:
            bitmap = page.render(scale=2.0)
            images.append(bitmap.to_pil().convert("RGB"))
            bitmap.close()
            page.close()
    finally:
        document.close()
    return images


def _extract_images(images, preferred):
    errors = []
    if preferred in {"auto", "paddleocr"}:
        try:
            return _paddle_images(images)
        except Exception as exc:
            errors.append(f"PaddleOCR unavailable: {exc}")
            if preferred == "paddleocr":
                raise RuntimeError(errors[-1]) from exc
    if preferred in {"auto", "tesseract"}:
        try:
            return _tesseract_images(images)
        except (ImportError, ModuleNotFoundError, RuntimeError, OSError) as exc:
            errors.append(f"Tesseract unavailable: {exc}")
    raise RuntimeError("; ".join(errors) or f"Unsupported OCR engine: {preferred}")


def extract_document(path, preferred="auto"):
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        embedded = _pdf_text(path)
        if all(page.text.strip() for page in embedded.pages):
            return embedded
        return _extract_images(_render_pdf(path), preferred)
    return _extract_images([path], preferred)
