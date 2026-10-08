import subprocess
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError

from apps.documents.services.local_workflow import Options
from apps.googleforms.creation import creation_schema
from apps.googleforms.generator import generate_apps_script
from tests.test_googleforms import activate_student, human_source


def question(key, **changes):
    return SimpleNamespace(
        **{
            "key": key,
            "text": "Repeated title",
            "type": "SHORT_TEXT",
            "help_text": "",
            "required": False,
            "options": Options(),
            "validation_rules": {},
            **changes,
        }
    )


@pytest.mark.django_db
def test_create_new_form_api_needs_no_existing_url(client, user):
    activate_student(user)
    batch, _ = human_source(user)
    response = client.post(
        "/api/v1/google-forms/scripts/",
        {
            "source_type": "RESPONSE_BATCH",
            "source_id": str(batch.id),
            "create_new_form": True,
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["form_id"] == ""
    assert "function createQuestionnaire()" in response.data["script"]
    assert "getItemById" in response.data["script"]


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "SINGLE_CHOICE"},
        {"type": "SINGLE_GRID", "validation_rules": {"rows": ["one"]}},
        {"type": "LINEAR_SCALE", "validation_rules": {"min": 2, "max": 5}},
        {
            "type": "SINGLE_CHOICE",
            "options": Options([SimpleNamespace(label="Label", value="different")]),
        },
    ],
)
def test_creation_rejects_unsupported_or_incomplete_schema(changes):
    with pytest.raises(ValidationError):
        creation_schema([question("q", **changes)])


def test_generated_script_creates_once_maps_ids_and_does_not_submit_on_creation(tmp_path):
    schema = creation_schema([question("a"), question("b")])
    script = generate_apps_script(
        job_id="test",
        form_id="",
        mappings={"a": "Repeated title", "b": "Repeated title"},
        responses=[{"id": "one", "answers": {"a": "A", "b": "B"}}],
        classification="HUMAN",
        form_schema=schema,
    )
    harness = r"""
const assert = require('node:assert/strict');
const store = new Map();
const properties = { getProperty: k => store.get(k) || null, setProperty: (k,v) => store.set(k,v) };
global.PropertiesService = { getScriptProperties: () => properties };
global.LockService = { getScriptLock: () => ({tryLock: () => true, releaseLock: () => {}}) };
let created = 0, submitted = 0;
const items = [];
const form = {
  getId: () => 'created-form', getTitle: () => 'Questionnaire',
  getEditUrl: () => 'edit-url', getPublishedUrl: () => 'answer-url',
  isAcceptingResponses: () => true,
  addTextItem() {
    const item = { id: items.length + 1, title: '',
      setTitle(v) { this.title=v; return this; }, setHelpText() { return this; },
      setRequired() { return this; }, getId() { return this.id; },
      getTitle() { return this.title; }, getType: () => 'TEXT',
      asTextItem() { return this; }, createResponse: v => ({value:v}),
    }; items.push(item); return item;
  },
  getItemById: id => items.find(item => item.id === id),
  createResponse: () => ({withItemResponse() { return this; }, submit() { submitted++; }}),
};
global.FormApp = { create: () => {created++; return form;}, openById: () => form, ItemType: { TEXT: 'TEXT' } };
"""
    assertions = r"""
assert.throws(() => previewMapping(), /createQuestionnaire/);
createQuestionnaire(); createQuestionnaire();
assert.equal(created, 1); assert.equal(items.length, 2); assert.equal(submitted, 0);
assert.equal(previewMapping().mappedQuestions, 2);
startSubmission(); startSubmission(); assert.equal(submitted, 1);
store.set('stf:test:form', JSON.stringify({id:'created-form', complete:false}));
assert.throws(() => createQuestionnaire(), /interrupted/);
assert.equal(created, 1);
"""
    path = tmp_path / "script.cjs"
    path.write_text(harness + script + assertions)
    result = subprocess.run(["node", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
