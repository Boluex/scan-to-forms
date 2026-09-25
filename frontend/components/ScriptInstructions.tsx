export default function ScriptInstructions() {
  return (
    <section className="mvp-panel">
      <h2>Submit to your existing Google Form</h2>
      <p>
        This script submits responses; it does not create a form. Use an account
        with edit access. ScanToForms has not verified ownership.
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
