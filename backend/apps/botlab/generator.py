import random
from datetime import date, time, timedelta

from apps.questionnaires.models import Question


def _option_values(question):
    return [option.value or option.label for option in question.options.all()]


def synthetic_answer(question, index, rng):
    options = _option_values(question)
    if question.type in (Question.Type.SINGLE_CHOICE, Question.Type.DROPDOWN, Question.Type.SINGLE_GRID):
        return rng.choice(options) if options else "Synthetic option"
    if question.type in (Question.Type.MULTIPLE_CHOICE, Question.Type.MULTIPLE_GRID):
        if not options:
            return ["Synthetic option"]
        return rng.sample(options, k=rng.randint(1, min(3, len(options))))
    if question.type in (Question.Type.LIKERT, Question.Type.LINEAR_SCALE):
        return rng.choice(options) if options else rng.randint(1, 5)
    if question.type == Question.Type.NUMBER:
        minimum = int(question.validation_rules.get("min", 18))
        maximum = int(question.validation_rules.get("max", max(minimum, 65)))
        return rng.randint(minimum, maximum)
    if question.type == Question.Type.DATE:
        return (date(2020, 1, 1) + timedelta(days=rng.randint(0, 2190))).isoformat()
    if question.type == Question.Type.TIME:
        return time(rng.randint(7, 20), rng.choice((0, 15, 30, 45))).isoformat(timespec="minutes")
    if question.type == Question.Type.PARAGRAPH:
        return f"Synthetic paragraph response {index} for testing this questionnaire workflow."
    return f"Synthetic answer {index}"


def generate_payloads(version, count, seed):
    rng = random.Random(seed)
    questions = list(version.questions.prefetch_related("options").order_by("position"))
    payloads = []
    for index in range(1, count + 1):
        answers = {}
        for question in questions:
            if not question.required and rng.random() < 0.08:
                answers[question.key] = None
            else:
                answers[question.key] = synthetic_answer(question, index, rng)
        payloads.append(answers)
    return payloads

