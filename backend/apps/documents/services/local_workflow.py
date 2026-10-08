"""Local drafts without database, queue, payment or notification mutations."""

import csv
import hashlib
import json
import random
import re
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

from django.core.files import File

from apps.botlab.generator import synthetic_answer
from apps.core.spreadsheets import safe_cell
from apps.documents.services.ocr import extract_document
from apps.documents.services.parser import detect_schema, map_answers
from apps.documents.validation import inspect_upload
from apps.orders.serializers import SchemaSerializer
from apps.questionnaires.integrity import answer_error


class Options(list):
    def all(self):
        return self


def load_schema(path):
    source = json.loads(Path(path).read_text())
    serializer = SchemaSerializer(data={"questions": source["questions"]})
    serializer.is_valid(raise_exception=True)
    questions = []
    for row in serializer.validated_data["questions"]:
        values = dict(row)
        values["options"] = Options(
            SimpleNamespace(
                **{
                    "value": o.get("value") or o["label"],
                    **o,
                }
            )
            for o in values.get("options", [])
        )
        for key, default in {
            "required": False,
            "validation_rules": {},
            "help_text": "",
            "template_page_number": None,
        }.items():
            values.setdefault(key, default)
        questions.append(SimpleNamespace(**values))
    if not questions:
        raise ValueError("The schema has no questions.")
    return sorted(questions, key=lambda q: q.position)


def inventory(
    folder, *, manifest=None, pages_per_respondent, expected_respondents=None, single=False
):
    root = Path(folder).resolve(strict=True)
    if not root.is_dir() or not 1 <= pages_per_respondent <= 100:
        raise ValueError("Use a source folder and 1–100 pages per respondent.")
    if manifest:
        rows = json.loads(Path(manifest).read_text())
        if not isinstance(rows, list):
            raise ValueError("Manifest must be an array of page assignments.")
    else:
        rows = []
        groups = [root] if single else sorted(p for p in root.iterdir() if p.is_dir())
        for group in groups:
            for file in sorted(group.iterdir()):
                if file.suffix.lower() not in {".png", ".jpg", ".jpeg", ".pdf"}:
                    continue
                match = re.fullmatch(r"page-(\d+)", file.stem, re.IGNORECASE)
                if not match or file.suffix.lower() == ".pdf":
                    raise ValueError(
                        "Use page-1.jpg, page-2.png, etc., or provide an explicit --manifest (required for PDFs)."
                    )
                rows.append(
                    {
                        "respondent": "R-0001" if single else group.name,
                        "page": int(match[1]),
                        "file": str(file.relative_to(root)),
                    }
                )
    if not rows:
        raise ValueError(
            "No assigned pages. Use respondent subfolders, --single-respondent, or --manifest."
        )
    groups, slots, sources, hashes = {}, set(), set(), {}
    for row in rows:
        respondent, page = row["respondent"], row["page"]
        if not isinstance(respondent, str) or not respondent.strip() or type(page) is not int:
            raise ValueError("Each assignment needs a respondent name and integer page.")
        if (respondent, page) in slots or not 1 <= page <= pages_per_respondent:
            raise ValueError("Duplicate or invalid respondent/page slot.")
        slots.add((respondent, page))
        path = (root / row["file"]).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Manifest paths must stay inside the source folder.")
        if path not in hashes:
            with path.open("rb") as stream:
                hashes[path] = inspect_upload(File(stream, name=path.name))
        info = hashes[path]
        source_page = row.get("source_page", 1)
        if type(source_page) is not int or not 1 <= source_page <= info["page_count"]:
            raise ValueError("Invalid PDF/image source page.")
        identity = (info["sha256"], source_page)
        if identity in sources:
            raise ValueError("The same physical source page is assigned more than once.")
        sources.add(identity)
        groups.setdefault(respondent, []).append(
            {
                "page": page,
                "file": str(path),
                "source_page": source_page,
                "sha256": info["sha256"],
            }
        )
    for respondent, pages in groups.items():
        if sorted(p["page"] for p in pages) != list(range(1, pages_per_respondent + 1)):
            raise ValueError(f"{respondent}: incomplete pages; expected 1–{pages_per_respondent}.")
        pages.sort(key=lambda p: p["page"])
    if expected_respondents is not None and len(groups) != expected_respondents:
        raise ValueError(f"Expected {expected_respondents} respondents, found {len(groups)}.")
    return groups


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def new_output(path):
    target = Path(path).resolve()
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    return target


def digitize(groups, output, *, questions=None, engine="paddleocr", progress=print):
    target = new_output(output)
    (target / "ocr").mkdir()
    write_json(target / "manifest.json", groups)
    records, cache = [], {}
    try:
        for respondent, pages in groups.items():
            regions = []
            for page in pages:
                source = Path(page["file"])
                if source not in cache:
                    if hashlib.sha256(source.read_bytes()).hexdigest() != page["sha256"]:
                        raise ValueError("Source changed after inventory. Recheck the input files.")
                    progress(f"OCR: {source.name}")
                    cache[source] = extract_document(source, preferred=engine)
                    write_json(target / "ocr" / f"{page['sha256']}.json", asdict(cache[source]))
                extracted = cache[source].pages[page["source_page"] - 1]
                for region in extracted.regions:
                    regions.append({**asdict(region), "template_page_number": page["page"]})
            if questions:
                values = [
                    {
                        "question_key": item["question"].key,
                        "value": item["value_text"] or None,
                        "status": "NEEDS_REVIEW",
                        "ocr_candidate_status": item["review_status"],
                        "confidence": item["confidence"],
                        "source_region": item["source_region"],
                        "details": item["raw_value"],
                    }
                    for item in map_answers(questions, regions)
                ]
                records.append({"respondent": respondent, "answers": values})
            else:
                records.append(
                    {"respondent": respondent, "detected_schema_candidates": detect_schema(regions)}
                )
            write_json(target / "draft.json", {"status": "NEEDS_REVIEW", "respondents": records})
        if questions:
            with (target / "responses-draft.csv").open(
                "w", newline="", encoding="utf-8-sig"
            ) as stream:
                writer = csv.writer(stream)
                writer.writerow(["respondent", "status", *[safe_cell(q.key) for q in questions]])
                for record in records:
                    writer.writerow(
                        [
                            safe_cell(record["respondent"]),
                            "NEEDS_REVIEW",
                            *[safe_cell(a["value"] or "") for a in record["answers"]],
                        ]
                    )
        write_json(
            target / "run.json",
            {
                "status": "NEEDS_REVIEW",
                "respondents": len(records),
                "pages": sum(map(len, groups.values())),
                "engine_requested": engine,
            },
        )
    except Exception as exc:
        write_json(
            target / "run.json",
            {
                "status": "FAILED",
                "error_type": type(exc).__name__,
                "completed_respondents": len(records),
            },
        )
        raise
    return target


def synthetic(questions, output, *, count, seed):
    if not 1 <= count <= 10000:
        raise ValueError("Choose 1–10000 synthetic TEST rows.")
    rng, records = random.Random(seed), []
    for index in range(1, count + 1):
        answers = {}
        for q in questions:
            value = synthetic_answer(q, index, rng)
            error = answer_error(SimpleNamespace(question=q, value_json=value, value_text=""))
            if error:
                raise ValueError(f"{q.key}: {error}")
            answers[q.key] = value
        records.append(
            {
                "sequence": index,
                "data_label": "SYNTHETIC TEST DATA — NOT HUMAN RESEARCH RESPONSES",
                "answers": answers,
            }
        )
    target = new_output(output)
    write_json(
        target / "synthetic-test-data.json",
        {"classification": "SYNTHETIC TEST DATA", "seed": seed, "responses": records},
    )
    with (target / "synthetic-test-data.csv").open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sequence", "data_label", *[safe_cell(q.key) for q in questions]])
        for row in records:
            writer.writerow(
                [
                    row["sequence"],
                    row["data_label"],
                    *[
                        safe_cell(
                            json.dumps(v, ensure_ascii=False) if isinstance(v, list | dict) else v
                        )
                        for v in row["answers"].values()
                    ],
                ]
            )
    return target
