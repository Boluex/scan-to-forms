"""Deterministic, schema-checked Google Form creation; no model-generated code."""

import json
import math

from rest_framework.exceptions import ValidationError


def creation_schema(questions):
    result = []
    simple = {"SHORT_TEXT", "PARAGRAPH", "NUMBER", "DATE", "TIME"}
    choices = {"SINGLE_CHOICE", "MULTIPLE_CHOICE", "DROPDOWN", "LIKERT"}
    for q in questions:
        options = list(q.options.all())
        values = [o.value or o.label for o in options]
        rules = q.validation_rules
        if not isinstance(rules, dict):
            raise ValidationError(f"{q.key}: validation rules must be an object.")
        if any((o.value or o.label) != o.label for o in options):
            raise ValidationError(f"{q.key}: new Forms require matching option labels and values.")
        item = {
            "key": q.key,
            "title": q.text,
            "help": q.help_text,
            "type": q.type,
            "required": q.required,
            "options": values,
        }
        if q.type in choices and values:
            if len(set(values)) != len(values):
                raise ValidationError(f"{q.key}: option labels must be unique.")
        elif q.type == "LINEAR_SCALE" or (q.type == "LIKERT" and not values):
            low, high = rules.get("min", 1), rules.get("max", 5)
            if (
                type(low) is not int
                or type(high) is not int
                or low not in (0, 1)
                or not 3 <= high <= 10
            ):
                raise ValidationError(
                    f"{q.key}: Google scales require lower bound 0/1 and upper bound 3–10."
                )
            item.update(type="LINEAR_SCALE", low=low, high=high)
        elif q.type in {"SINGLE_GRID", "MULTIPLE_GRID"}:
            for field in ("rows", "columns"):
                entries = rules.get(field)
                if (
                    not isinstance(entries, list)
                    or not entries
                    or any(not isinstance(v, str) or not v.strip() for v in entries)
                    or len(set(entries)) != len(entries)
                ):
                    raise ValidationError(f"{q.key}: configure unique nonempty grid {field}.")
                item[field] = entries
        elif q.type not in simple:
            raise ValidationError(f"{q.key}: unsupported question or missing choices ({q.type}).")
        if q.type == "NUMBER":
            for field in ("min", "max"):
                if field in rules:
                    value = rules[field]
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, int | float)
                        or not math.isfinite(value)
                    ):
                        raise ValidationError(f"{q.key}: numeric bounds must be numbers.")
                    item[field] = value
        if "min" in item and "max" in item and item["min"] > item["max"]:
            raise ValidationError(f"{q.key}: minimum exceeds maximum.")
        result.append(item)
    if not result:
        raise ValidationError("Review at least one question before creating a Form.")
    return result


def creation_helpers(schema, title):
    payload = json.dumps({"title": title, "questions": schema}, ensure_ascii=False, allow_nan=False)
    return (
        "const STF_FORM_SCHEMA = Object.freeze("
        + payload
        + ");\n"
        + r"""
function formStateKey_() { return `stf:${STF_CONFIG.datasetId}:form`; }
function formItemKey_(key) { return `stf:${STF_CONFIG.datasetId}:item:${key}`; }

function createdFormState_() {
  const raw = PropertiesService.getScriptProperties().getProperty(formStateKey_());
  return raw ? JSON.parse(raw) : null;
}

function createQuestionnaire() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) throw new Error('Another run is active.');
  try {
    const props = PropertiesService.getScriptProperties();
    let state = createdFormState_();
    if (state && !state.complete) {
      throw new Error('Creation was interrupted. Inspect https://docs.google.com/forms/d/' + state.id + '/edit and contact support. No second Form was created.');
    }
    if (!state) {
      const form = FormApp.create(STF_FORM_SCHEMA.title);
      state = { id: form.getId(), complete: false };
      props.setProperty(formStateKey_(), JSON.stringify(state));
      STF_FORM_SCHEMA.questions.forEach((q) => {
        let item;
        switch (q.type) {
          case 'SHORT_TEXT': item = form.addTextItem(); break;
          case 'NUMBER': {
            item = form.addTextItem();
            const rule = FormApp.createTextValidation().requireNumber();
            if (q.min !== undefined && q.max !== undefined) rule.requireNumberBetween(q.min, q.max);
            else if (q.min !== undefined) rule.requireNumberGreaterThanOrEqualTo(q.min);
            else if (q.max !== undefined) rule.requireNumberLessThanOrEqualTo(q.max);
            item.setValidation(rule.build());
            break;
          }
          case 'PARAGRAPH': item = form.addParagraphTextItem(); break;
          case 'SINGLE_CHOICE':
          case 'LIKERT': item = form.addMultipleChoiceItem().setChoiceValues(q.options); break;
          case 'MULTIPLE_CHOICE': item = form.addCheckboxItem().setChoiceValues(q.options); break;
          case 'DROPDOWN': item = form.addListItem().setChoiceValues(q.options); break;
          case 'LINEAR_SCALE': item = form.addScaleItem().setBounds(q.low, q.high); break;
          case 'SINGLE_GRID': item = form.addGridItem().setRows(q.rows).setColumns(q.columns); break;
          case 'MULTIPLE_GRID': item = form.addCheckboxGridItem().setRows(q.rows).setColumns(q.columns); break;
          case 'DATE': item = form.addDateItem().setIncludesYear(true); break;
          case 'TIME': item = form.addTimeItem(); break;
          default: throw new Error('Unsupported type: ' + q.type);
        }
        item.setTitle(q.title).setHelpText(q.help).setRequired(q.required);
        props.setProperty(formItemKey_(q.key), String(item.getId()));
      });
      state.complete = true;
      props.setProperty(formStateKey_(), JSON.stringify(state));
    }
    const form = FormApp.openById(state.id);
    console.log('Edit Form: ' + form.getEditUrl());
    console.log('Respondent link: ' + form.getPublishedUrl());
    console.log('Inspect questions and publish/access settings. No responses were submitted.');
    return { editUrl: form.getEditUrl(), respondentUrl: form.getPublishedUrl() };
  } finally { lock.releaseLock(); }
}
"""
    )
