import re
from difflib import SequenceMatcher

from apps.questionnaires.models import Answer, Question, QuestionOption

PARSER_VERSION = "heuristic-0.1"
QUESTION_PATTERN = re.compile(r"^(?:q(?:uestion)?\s*)?\d+[.)\s-]+(.{3,})$", re.IGNORECASE)
OPTION_PATTERN = re.compile(r"^(?:[□☐☑✓✔○◯()]|[a-z][.)])\s*(.{1,})$", re.IGNORECASE)


def _normalize(value):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s?]", " ", value.lower())).strip()


def detect_schema(regions):
    questions = []
    current = None
    for region in regions:
        text = region["text"].strip()
        match = QUESTION_PATTERN.match(text)
        looks_like_question = bool(match) or text.endswith("?")
        if looks_like_question:
            question_text = (match.group(1) if match else text).strip()
            current = {
                "key": f"q{len(questions) + 1}",
                "position": len(questions) + 1,
                "text": question_text,
                "type": Question.Type.SHORT_TEXT,
                "required": False,
                "source_region": region.get("bounding_box", {}),
                "template_page_number": region.get("template_page_number"),
                "options": [],
            }
            questions.append(current)
            continue
        option = OPTION_PATTERN.match(text)
        if current and option:
            current["options"].append(
                {"key": f"o{len(current['options']) + 1}", "position": len(current["options"]) + 1, "label": option.group(1).strip()}
            )
            current["type"] = Question.Type.SINGLE_CHOICE
    return questions


def map_answers(questions, regions):
    questions = list(questions)
    mappings = []
    for question in questions:
        candidate_regions = (
            [region for region in regions if region.get("template_page_number") == question.template_page_number]
            if question.template_page_number
            else regions
        )
        normalized_regions = [_normalize(region["text"]) for region in candidate_regions]
        needle = _normalize(question.text)
        scores = [SequenceMatcher(None, needle, candidate).ratio() for candidate in normalized_regions]
        match_index = max(range(len(scores)), key=scores.__getitem__) if scores else None
        match_score = scores[match_index] if match_index is not None else 0
        value = ""
        confidence = 0.0
        source_region = {}
        if match_index is not None and match_score >= 0.48 and match_index + 1 < len(candidate_regions):
            candidate = candidate_regions[match_index + 1]
            if max((SequenceMatcher(None, _normalize(q.text), normalized_regions[match_index + 1]).ratio() for q in questions), default=0) < 0.62:
                value = candidate["text"].strip()
                confidence = min(float(candidate.get("confidence") or 0.5), match_score)
                source_region = candidate.get("bounding_box", {})
        review_status = (
            Answer.ReviewStatus.AUTO_HIGH
            if confidence >= 0.85
            else Answer.ReviewStatus.AUTO_MEDIUM
            if confidence >= 0.65
            else Answer.ReviewStatus.NEEDS_REVIEW
        )
        mappings.append(
            {
                "question": question,
                "value_text": value,
                "confidence": confidence,
                "review_status": review_status,
                "source_region": source_region,
                "raw_value": {"question_match": match_score},
            }
        )
    return mappings


def persist_detected_schema(version, detected):
    if version.questions.exists():
        return 0
    for data in detected:
        options = data.pop("options", [])
        question = Question.objects.create(version=version, **data)
        QuestionOption.objects.bulk_create([QuestionOption(question=question, **option) for option in options])
    return len(detected)
