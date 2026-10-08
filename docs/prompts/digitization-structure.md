# Task: extract questionnaire structure

Apply the common instruction. Inputs are source pages, page inventory, OCR regions and the structure response schema. Extract the blank questionnaire structure even if the supplied pages contain completed answers. Do not copy respondent answers into titles, option lists or help text.

Identify title, introductory instructions, sections, question labels/text, answer type, option labels and order, scale endpoints/labels, table row labels and column labels. Preserve separate questions and rows. Record requiredness only if it is supported by the document; otherwise use null.

Detect wrapped question/option text and continuations onto adjacent pages. Link a continuation to its original question rather than creating another question. If adjacent context is absent, return an unresolved continuation. Do not merge different questions solely because their words are similar.

Use supplied stable identifiers. If internal keys must be assigned, preserve the original printed label separately and avoid duplicates. Record the source evidence for every element.

Mark uncertain question types, unreadable options, duplicate labels, missing pages and unsupported structures as unresolved. Do not invent branching rules or convert unsupported content silently. Return the pages actually inspected and a complete ordered inventory for human comparison with the originals.
