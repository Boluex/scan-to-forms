export default function ScriptInstructions({ createNewForm = false }: { createNewForm?: boolean }) {
  return (
    <section className="mvp-panel">
      <h2>{createNewForm ? "Create your Google Form and import reviewed answers" : "Submit to your existing Google Form"}</h2>
      <p>
        {createNewForm
          ? "Use the Google account that should own your new Form. Creating the questionnaire and importing its answers are separate steps."
          : "Use an account with edit access. Open your Form in editing mode and copy the address ending in /edit. A forms.gle or public answering link cannot be used. ScanToForms has not verified ownership."}
      </p>
      <ol className="instructions">
        <li>
          Go to{" "}
          <a href="https://script.google.com" target="_blank" rel="noreferrer">
            script.google.com
          </a>
          .
        </li>
        <li>Create a new project.</li>
        <li>Delete the default code.</li>
        <li>Paste the ScanToForms script.</li>
        <li>Save.</li>
        {createNewForm && <>
          <li>Select <code>createQuestionnaire</code> in the function selector and click Run. Authorize Google Forms access when prompted.</li>
          <li>Open the Edit Form URL in the execution log. Inspect every question, option and scale. The respondent link is for answering; check publish/access settings before sharing it.</li>
          <li>Return to this same script project to import the reviewed answers. Creation itself has not submitted any responses.</li>
        </>}
        <li>
          Run <code>previewMapping()</code>.
        </li>
        <li>Verify the mapped Google Form questions in the execution log.</li>
        <li>
          Run <code>startSubmission()</code>.
        </li>
        <li>
          Authorize Google when prompted. Google may request authorization when
          you first run the preview.
        </li>
        <li>
          Run <code>continueSubmission()</code> if more responses remain.
        </li>
        <li>
          Run <code>submissionStatus()</code> to inspect progress.
        </li>
        <li>Open the Google Form and verify the Responses tab.</li>
      </ol>
      <p>
        If the log reports a missing question, invalid choice, incomplete creation or permission problem, stop and contact support with your order reference and error text. No public web-app deployment is required.
      </p>
      <p>
        Normal reruns in the same script project track submitted records. Do not
        create a second submission project for the same dataset. If execution
        fails, inspect the form before retrying: a submission interrupted before
        its progress marker is saved can be duplicated.
      </p>
      <p>
        Never share your Google password. ScanToForms cannot see your Google
        execution status.
      </p>
    </section>
  );
}
