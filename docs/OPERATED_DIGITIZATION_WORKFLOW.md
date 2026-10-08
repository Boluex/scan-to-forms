# Admin-operated digitization service

Updated after the owner's correction: **payment is verified before processing**. Earlier proposals for payment after processing are withdrawn.

## Customer and administrator journey

1. Customer creates a request, chooses a new or existing Google Form, and uploads questionnaire pages.
2. The completed submission creates an administrator inbox notification and, when configured/subscribed, a Firebase push delivery.
3. Customer follows the bank instructions and claims payment. Administrators receive a payment-review alert. The claim does not start processing.
4. An authorized administrator verifies the payment, reviews/prepares the schema, and starts processing from the dashboard or `scripts/run-order.sh`.
5. The Ubuntu worker runs PaddleOCR. An administrator reviews page grouping and answers against source images, corrects them and confirms respondents. An additional LLM is optional and is not connected in this release.
6. The administrator prepares the Google Forms script, marks the approved result READY, and the customer receives an inbox notification plus optional push.
7. Customer opens the order, downloads results and follows the selected Google Forms instructions. No second payment is required.

If the Ubuntu machine is off, queued jobs wait. Inbox/order status remains available when push is denied or delayed. Firebase credentials, sender activation and real-device tests are still needed; see [FIREBASE_SETUP.md](FIREBASE_SETUP.md). No Gmail API is needed for these order events.

## Payment and review boundaries

Verified payment is required for schema preparation, processing and delivery. Delivery also requires all reviewed respondents, complete page assignments and a prepared script. Local folder tools produce private drafts and never verify payment, import answers into the website, release orders or notify customers. The paid-order command uses the same business-service checks as the web dashboard.

Customer APIs remain owner-scoped. An administrator's terminal email selects an existing account for authorization/auditing; running management commands also requires trusted access to the server environment. The command never creates an admin account.

## Multiple upload batches

70 respondents × 4 pages = **280 physical pages and 70 logical responses**. Users can upload those pages in multiple selections. The next selection must use the correct global starting image number (for example, 141 after 140 images), or an explicit respondent/page slot. A partial order cannot be submitted for payment until its required pages are complete.

Supported grouping modes are ordered images, manual respondent/page slots, and one complete PDF per respondent. Filenames and upload order do not reliably establish identity for arbitrarily shuffled respondents. Page review remains required. Four images from one person are not four respondents.

## Google Forms delivery

For an existing Form, the administrator supplies the edit URL/ID and mappings. For a new Form, the script creates approved questions, stores item IDs and prints edit/respondent links; creating it does not submit answers. The customer previews and then explicitly starts import. Instructions appear beside the delivered script.

Supported creation types: short text, paragraph, number, single/multiple choice, dropdown, Likert, linear scale, date, time and configured grids. Invalid/missing options, unsupported scale bounds and unconfigured grids are rejected. This is a questionnaire-data conversion, not reproduction of a photograph's typography. The current schema does not model sections/branching or file-upload questions. New-Form choice labels and values must match; unsupported definitions need operator correction.

The existing paid digitization order still requires at least one respondent. Questionnaire-only customer orders without respondent data need a separate service/model change; do not create fake respondents to bypass that constraint.

## Accuracy and readiness

The real four-page trial proved OCR execution and grouping, not universal extraction. Its structure required manual preparation, and ticks/grid answers required visual transcription. The parser now leaves structured selections pending rather than treating printed options as answers. PaddleOCR plus calibrated layout/mark detection may support known templates without an LLM; robust mark detection is still future work.

No extra AI API/model is required for the current reviewed service. [AI_DIGITIZATION_PIPELINE.md](AI_DIGITIZATION_PIPELINE.md) describes an optional later improvement, not a launch dependency or accuracy guarantee.

Local regression tests cover the 70×4 grouping case, unpaid processing denial, admin push outbox creation, new/existing Form delivery and the generated script's behavior under a mocked Google runtime. Google-account execution and actual Firebase device delivery remain external acceptance tasks. Synthetic rows remain labelled TEST data and are not submitted to research Forms.

See [terminal usage](LOCAL_WORKFLOWS.md) and [customer setup guide](GOOGLE_FORMS_DELIVERY_GUIDE.md).
