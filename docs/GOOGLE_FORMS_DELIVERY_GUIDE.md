# Customer Google Forms setup and delivery guide

This guide defines the instructions to show with a paid, approved result. Both new-Form creation and existing-Form submission are implemented for reviewed digitization orders. Local tests do not replace a live Google-account acceptance test.

## Result page

Payment is verified before processing. While processing/review is underway, results remain locked. Once approved and READY, show the result version, CSV/XLSX, Copy code, Download .gs, and the selected setup path below. Explain whether the result contains only questionnaire questions or also reviewed respondent answers.

Use numbered steps and the exact function names in the delivered script. Explain success, expected logs and recovery on the same page. The customer should not need to know PaddleOCR, provider names, queues or database terminology.

## Path A: I want a new Google Form

No existing Form URL should be required to create one.

1. Open Google Apps Script while signed into the Google account that should own the Form.
2. Create a new project and give it a recognisable name, such as the order reference.
3. Open `Code.gs`, replace its starter code with the supplied **Create questionnaire** code, and save.
4. Select the creation function named in the instructions (`createQuestionnaire`) and run it. Review Google's authorization request and authorize the intended account.
5. The completed run should print an **Edit Form URL** and a **Respondent URL**. Open the edit URL to inspect questions, options, sections and scales. The respondent URL is the answering link; keep it separate from the edit URL. Check the Form's publish/access settings before sharing it.
6. If the order contains only questionnaire conversion, setup ends after inspection and the customer's sharing configuration.
7. If the order also contains reviewed answers, proceed to the supplied **Import reviewed answers** instructions. Form creation itself must not silently submit responses.

The implementation uses a deterministic generator based on the approved schema. Google provides `FormApp.create(...)`; Form instances expose edit and respondent URLs. Record question-to-item IDs in the same script project, persist the created Form ID, lock concurrent runs and handle interrupted creation. Normal reruns must reuse the existing created Form rather than create duplicates. A version mismatch or partial creation must produce an explicit repair/review state, not a silent rebuild. See [FormApp](https://developers.google.com/apps-script/reference/forms/form-app) and [Form](https://developers.google.com/apps-script/reference/forms/form).

## Path B: I already have a Google Form — existing implementation

### Get the correct link

Open the Form in editing mode using an account with edit access. Copy its browser address, normally:

```text
https://docs.google.com/forms/d/FORM_ID/edit
```

The current ScanToForms validator accepts that edit link or its Form ID. It does not accept a `forms.gle` short link or the public `/forms/d/e/.../viewform` answering link. Do not ask customers for a Google password. ScanToForms sign-in does not establish permission to edit a destination Form.

The administrator must map every source question to the destination and check types, options and grid row/column order before preparing delivery. The current script maps by question title and rejects duplicate titles. A matching title alone does not prove that the answer type or options are compatible. New Forms use stored item IDs; existing Forms still use title mappings. Stronger type/option preflight for existing Forms remains a future improvement.

### Paste and run the delivered code

1. Visit [Google Apps Script](https://script.google.com), create a new project and name it with the order reference.
2. Open `Code.gs`, replace the starter code with the complete ScanToForms script and save.
3. Select `previewMapping` from the function selector and click Run. Review Google's authorization request for the account with edit access. If a school/organisation policy blocks execution, contact its administrator rather than bypassing the restriction.
4. Read the execution log. Check the Form title, response count and every mapped question/type. This preview does not submit responses. Stop if the destination or mappings are wrong and request a corrected script.
5. Select `startSubmission` and run it to submit the reviewed records.
6. The current script processes up to 40 records per execution. If the log reports remaining records, run `continueSubmission` again in the same project.
7. Run `submissionStatus` to inspect progress. When it reports complete, open the Form's Responses view and check the imported data. Account for any responses that already existed.

Google documents [creating projects](https://developers.google.com/apps-script/guides/projects) and [authorization](https://developers.google.com/apps-script/guides/services/authorization). Menu wording can change; instructions should be verified during the live acceptance test. Running these standalone functions does not require deploying them as a public web app.

### If something goes wrong

| Message/symptom | Customer action |
| --- | --- |
| Cannot open Form / permission denied | Check the signed-in account and use the Form's edit URL |
| Missing or duplicate question title | Contact ScanToForms with the order reference and error text; mapping needs correction |
| Form not accepting responses | Check the destination Form's response settings |
| Invalid choice/grid value | Stop and request a mapping/data review; do not substitute answers |
| Run stops or times out | Inspect the last log and actual Form responses before continuing |
| More responses remain | Run `continueSubmission` in the same project |

Keep one submission project for each delivered dataset. Normal reruns remember progress in that project, but an interruption after submission and before recording progress can still create a duplicate on retry. Creating a second project loses that progress. Do not promise exactly-once delivery.

The current app cannot see execution inside the customer's Google account. Show **Result delivered** separately from any customer-reported **Google import complete**. An app notification must not claim the Google import succeeded without evidence.
