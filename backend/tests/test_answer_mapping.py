import pytest

from apps.documents.services.parser import map_answers
from apps.questionnaires.models import Question


def regions(*texts):
    return [{"text": text, "confidence": 0.99, "template_page_number": 1} for text in texts]


@pytest.mark.parametrize(
    "kind", ["SINGLE_CHOICE", "MULTIPLE_CHOICE", "LIKERT", "SINGLE_GRID", "LINEAR_SCALE"]
)
def test_text_confidence_cannot_determine_a_selected_option(kind):
    question = Question(text="Are you satisfied?", type=kind, template_page_number=1)
    result = map_answers(
        [question], regions("Are you satisfied?", "Satisfied [] Neutral [] Dissatisfied []")
    )[0]
    assert result["value_text"] == ""
    assert result["review_status"] == "NEEDS_REVIEW"
    assert result["confidence"] == 0
    assert result["raw_value"]["reason"] == "structured_answer_requires_review"


def test_unanswered_wrapped_prompt_is_not_its_own_answer():
    question = Question(
        text="What could improve waste management in your household?",
        type="PARAGRAPH",
        template_page_number=1,
    )
    result = map_answers(
        [question],
        regions(
            "What could improve waste management in",
            "your household?",
            "E2. Who should take the lead?",
        ),
    )[0]
    assert result["value_text"] == ""
    assert result["review_status"] == "NEEDS_REVIEW"


@pytest.mark.parametrize(
    "candidate",
    [
        "SECTION A: CHARACTERISTICS",
        "PART 2: Neighbourhood",
        "C12",
        "E2. Who should take the lead?",
        "Yes [] No []",
        "________",
    ],
)
def test_document_structure_is_not_a_free_text_answer(candidate):
    question = Question(text="Street / area?", type="SHORT_TEXT", template_page_number=1)
    assert map_answers([question], regions("Street / area?", candidate))[0]["value_text"] == ""


def test_free_text_answer_still_maps_within_its_assigned_page():
    question = Question(text="What is your department?", type="SHORT_TEXT", template_page_number=1)
    result = map_answers([question], regions("What is your department?", "Computer Science"))[0]
    assert result["value_text"] == "Computer Science"
    assert result["review_status"] == "AUTO_HIGH"
