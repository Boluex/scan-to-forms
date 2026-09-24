import csv
from io import BytesIO, StringIO

from openpyxl import Workbook

from apps.core.spreadsheets import safe_cell
from apps.questionnaires.integrity import final_responses


def batch_table(batch):
    questions = list(batch.questionnaire_version.questions.order_by("position"))
    responses = final_responses(batch)
    headers = ["response_id", "respondent_reference", "status"] + [question.text for question in questions]
    rows = []
    for response in responses:
        answers = {answer.question_id: answer for answer in response.answers.all()}
        row = [str(response.id), response.respondent_reference, response.status]
        for question in questions:
            answer = answers.get(question.id)
            if not answer:
                row.append("")
            elif answer.value_json not in ({}, [], None):
                value = answer.value_json
                row.append("; ".join(map(str, value)) if isinstance(value, list) else str(value))
            else:
                row.append(answer.value_text)
        rows.append(row)
    return [safe_cell(v) for v in headers], [[safe_cell(v) for v in row] for row in rows]


def render_csv(batch):
    output = StringIO(newline="")
    writer = csv.writer(output)
    headers, rows = batch_table(batch)
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig"), len(rows)


def render_xlsx(batch):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("Responses")
    headers, rows = batch_table(batch)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue(), len(rows)

