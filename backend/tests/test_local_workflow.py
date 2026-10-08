import json
from types import SimpleNamespace

import pytest
from PIL import Image

from apps.documents.services.local_workflow import (
    Options,
    digitize,
    inventory,
    load_schema,
    synthetic,
)
from apps.documents.services.ocr import DocumentOutput, PageOutput, Region


def pages(root, count=2):
    root.mkdir()
    for i in range(1, count + 1):
        Image.new("RGB", (30, 30), (i, 20, 40)).save(root / f"page-{i}.png")


def test_local_inventory_does_not_guess_shuffled_whatsapp_names(tmp_path):
    pages(tmp_path / "source")
    (tmp_path / "source/page-1.png").rename(tmp_path / "source/WhatsApp image.png")
    with pytest.raises(ValueError, match="explicit --manifest"):
        inventory(tmp_path / "source", pages_per_respondent=2, single=True)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {"respondent": "R-0001", "page": 2, "file": "page-2.png"},
                {"respondent": "R-0001", "page": 1, "file": "WhatsApp image.png"},
            ]
        )
    )
    grouped = inventory(
        tmp_path / "source", pages_per_respondent=2, manifest=manifest, expected_respondents=1
    )
    assert [p["page"] for p in grouped["R-0001"]] == [1, 2]


def test_local_inventory_missing_duplicate_and_escape(tmp_path):
    pages(tmp_path / "source")
    with pytest.raises(ValueError, match="incomplete"):
        inventory(tmp_path / "source", pages_per_respondent=3, single=True)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"respondent": "one", "page": n, "file": "page-1.png"} for n in [1, 2]])
    )
    with pytest.raises(ValueError, match="more than once"):
        inventory(tmp_path / "source", pages_per_respondent=2, manifest=manifest)
    outside = tmp_path / "outside.png"
    outside.write_bytes((tmp_path / "source/page-1.png").read_bytes())
    manifest.write_text(json.dumps([{"respondent": "one", "page": 1, "file": "../outside.png"}]))
    with pytest.raises(ValueError, match="inside"):
        inventory(tmp_path / "source", pages_per_respondent=1, manifest=manifest)


def test_local_ocr_keeps_unselected_options_pending(tmp_path, monkeypatch):
    pages(tmp_path / "source", 1)
    groups = inventory(tmp_path / "source", pages_per_respondent=1, single=True)
    output = DocumentOutput(
        "stub",
        "test",
        [
            PageOutput(
                1,
                30,
                30,
                "Sex?\nMale Female",
                0.99,
                [
                    Region("Sex?", 0.99, {}),
                    Region("Male Female", 0.99, {}),
                ],
                {},
            )
        ],
    )
    monkeypatch.setattr(
        "apps.documents.services.local_workflow.extract_document", lambda *a, **k: output
    )
    q = SimpleNamespace(key="q1", text="Sex?", type="SINGLE_CHOICE", template_page_number=1)
    target = digitize(groups, tmp_path / "output", questions=[q])
    draft = json.loads((target / "draft.json").read_text())
    assert draft["respondents"][0]["answers"][0]["value"] is None
    assert draft["status"] == "NEEDS_REVIEW"
    with pytest.raises(FileExistsError):
        digitize(groups, target, questions=[q])


def test_synthetic_grids_and_scales_are_valid_reproducible_and_labelled(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "key": "grid",
                        "position": 1,
                        "text": "Grid",
                        "type": "SINGLE_GRID",
                        "validation_rules": {"rows": ["A", "B"], "columns": ["Yes", "No"]},
                    },
                    {
                        "key": "scale",
                        "position": 2,
                        "text": "Scale",
                        "type": "LINEAR_SCALE",
                        "validation_rules": {"min": 7, "max": 10},
                    },
                ]
            }
        )
    )
    questions = load_schema(schema)
    a = synthetic(questions, tmp_path / "a", count=70, seed=17)
    b = synthetic(questions, tmp_path / "b", count=70, seed=17)
    assert (a / "synthetic-test-data.json").read_bytes() == (
        b / "synthetic-test-data.json"
    ).read_bytes()
    data = json.loads((a / "synthetic-test-data.json").read_text())
    assert len(data["responses"]) == 70
    for row in data["responses"]:
        assert row["data_label"].startswith("SYNTHETIC TEST DATA")
        assert len(row["answers"]["grid"]) == 2
        assert 7 <= row["answers"]["scale"] <= 10


def test_invalid_grid_cannot_produce_synthetic_success(tmp_path):
    q = SimpleNamespace(key="g", type="MULTIPLE_GRID", options=Options(), validation_rules={})
    with pytest.raises(ValueError, match="configured rows"):
        synthetic([q], tmp_path / "output", count=1, seed=1)
    assert not (tmp_path / "output").exists()
