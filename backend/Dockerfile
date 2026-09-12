FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core libgl1 libglib2.0-0 libmagic1 tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt requirements/base.txt
RUN pip install -r requirements/base.txt

COPY . .

FROM base AS development
COPY requirements/dev.txt requirements/dev.txt
RUN pip install -r requirements/dev.txt

FROM base AS ocr-worker
COPY requirements/ocr.txt requirements/ocr.txt
RUN pip install -r requirements/ocr.txt
CMD ["celery", "-A", "config", "worker", "-l", "info"]

FROM base AS production
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app
USER appuser
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]

FROM ocr-worker AS ocr-production
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/media /home/appuser/.paddlex \
    && chown -R appuser:appuser /app /home/appuser/.paddlex
USER appuser
CMD ["celery", "-A", "config", "worker", "-l", "info", "--concurrency", "1"]
