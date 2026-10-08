import re
from difflib import SequenceMatcher

from apps.questionnaires.models import Answer, Question, QuestionOption

PARSER_VERSION = "heuristic-0.2"
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
                {
                    "key": f"o{len(current['options']) + 1}",
                    "position": len(current["options"]) + 1,
                    "label": option.group(1).strip(),
                }
            )
            current["type"] = Question.Type.SINGLE_CHOICE
    return questions


def map_answers(questions, regions):
    questions = list(questions)
    mappings = []
    for question in questions:
        # Text OCR does not locate a handwritten tick inside an option/grid cell.
        # Its recognition confidence must never become selection confidence.
        if question.type in (
            Question.Type.SINGLE_CHOICE,
            Question.Type.MULTIPLE_CHOICE,
            Question.Type.DROPDOWN,
            Question.Type.LIKERT,
            Question.Type.LINEAR_SCALE,
            Question.Type.SINGLE_GRID,
            Question.Type.MULTIPLE_GRID,
        ):
            mappings.append(
                {
                    "question": question,
                    "value_text": "",
                    "confidence": 0.0,
                    "review_status": Answer.ReviewStatus.NEEDS_REVIEW,
                    "source_region": {},
                    "raw_value": {"reason": "structured_answer_requires_review"},
                }
            )
            continue
        candidate_regions = (
            [
                region
                for region in regions
                if region.get("template_page_number") == question.template_page_number
            ]
            if question.template_page_number
            else regions
        )
        normalized_regions = [_normalize(region["text"]) for region in candidate_regions]
        needle = _normalize(question.text)
        scores = [
            SequenceMatcher(None, needle, candidate).ratio() for candidate in normalized_regions
        ]
        match_index = max(range(len(scores)), key=scores.__getitem__) if scores else None
        match_score = scores[match_index] if match_index is not None else 0
        value = ""
        confidence = 0.0
        source_region = {}
        if (
            match_index is not None
            and match_score >= 0.48
            and match_index + 1 < len(candidate_regions)
        ):
            candidate = candidate_regions[match_index + 1]
            candidate_text = candidate["text"].strip()
            candidate_normalized = normalized_regions[match_index + 1]
            # Wrapped prompts, section headings, printed checkboxes and row IDs
            # are document structure, not a respondent's free-text answer.
            prompt_fragment = bool(candidate_normalized) and set(
                candidate_normalized.split()
            ) <= set(needle.split())
            document_structure = bool(
                re.match(
                    r"^(?:SECTION\b|PART\s+\d|END OF QUESTIONNAIRE\b|[A-Z]{1,3}\d+(?:[.)\s:]|$))",
                    candidate_text,
                    re.IGNORECASE,
                )
                or re.search(r"\[\s*\]|[□☐☑]", candidate_text)
                or not any(character.isalnum() for character in candidate_normalized)
            )
            if (
                not prompt_fragment
                and not document_structure
                and max(
                    (
                        SequenceMatcher(None, _normalize(q.text), candidate_normalized).ratio()
                        for q in questions
                    ),
                    default=0,
                )
                < 0.62
            ):
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
        QuestionOption.objects.bulk_create(
            [QuestionOption(question=question, **option) for option in options]
        )
    return len(detected)
