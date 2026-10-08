# Task: extract one respondent's answers

Apply the common instruction. Inputs are the approved questionnaire schema, one respondent's assigned pages/crops, OCR regions and the answer response schema. Do not change question wording, options, grid columns, requiredness or question identifiers.

Return one entry for every requested question key. For each choice or table row, locate the visible mark relative to its own option/column label. A printed checkbox, option text, question number, row label or OCR line adjacent to a question is not a selected answer.

Inspect the base/location of ticks, not just a stroke extending into a neighbouring column. Preserve wrapped option text and source page context. Return stable approved option/row/column identifiers and use their specified types.

Use CANDIDATE only when there is source evidence for a value. Use BLANK with null only if the complete answer area is visible and unmarked. Use UNCLEAR for faint/unreadable content, CONFLICT for incompatible/multiple marks, and NOT_VISIBLE when the relevant source is absent or cropped. Preserve potentially conflicting marks for the reviewer instead of choosing a winner.

Transcribe handwriting only when legible. Never fill missing answers from other respondents or other rows. An explicit user clarification may be included only with its supplied provenance; never represent it as an image observation.

Attach page/crop/region references and concise observations. If you are a text-only model, do not claim visual evidence for marks; flag those selections for human review. All extracted values remain drafts regardless of apparent certainty.
