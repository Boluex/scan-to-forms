import Link from "next/link";
export default function Home() {
  return (
    <>
      <header className="mvp-nav">
        <Link href="/" className="brand">
          ScanToForms
        </Link>
        <nav aria-label="Main navigation">
          <Link href="/digitize">Digitize Questionnaire</Link>
          <Link href="/synthetic">Synthetic Test Data</Link>
          <Link href="/orders">My Orders</Link>
          <Link href="/login">Log in</Link>
        </nav>
      </header>
      <main className="mvp-content">
        <section className="mvp-hero">
          <p className="eyebrow">
            Paper to structured responses · Controlled beta
          </p>
          <h1>Turn Paper Questionnaires Into Google Form Responses</h1>
          <p>
            Upload completed questionnaires, review responses with our operator,
            and receive a Google Apps Script for your existing form.
          </p>
          <div className="button-row">
            <Link className="btn btn-primary" href="/digitize">
              Digitize Questionnaire
            </Link>
            <Link className="btn btn-secondary" href="/synthetic">
              Synthetic Test Data
            </Link>
          </div>
        </section>
        <section className="mvp-services">
          <article className="mvp-panel">
            <h2>Digitize completed questionnaires</h2>
            <p>
              Keep every respondent’s pages together. Upload ordered images,
              capture one page at a time, or upload one complete PDF per
              respondent.
            </p>
            <p>
              120 respondents with four pages each means 480 uploaded pages and
              120 logical responses. Uncertain pages and answers need operator
              review.
            </p>
            <ol>
              <li>Set up your job and upload the completed questionnaires.</li>
              <li>Check the page count and pay by bank transfer.</li>
              <li>
                We verify payment, prepare the data, and resolve review issues.
              </li>
              <li>
                Copy your Apps Script, check its mapping, and run it in your
                Google account.
              </li>
            </ol>
            <Link href="/digitize">Start digitization →</Link>
          </article>
          <article className="mvp-panel">
            <h2>Synthetic Test Data</h2>
            <p>
              <strong>
                SYNTHETIC TEST DATA — not real research respondents.
              </strong>
            </p>
            <p>
              Upload one blank questionnaire as a PDF or images, choose a
              response count, and send instructions. An operator prepares and
              checks a labelled dataset for testing forms and data workflows.
            </p>
            <p>
              Pay by bank transfer. We’ll notify you when your order is ready.
              Labelled CSV is supported; synthetic submission to Google Forms is
              not enabled in this beta.
            </p>
            <Link href="/synthetic">Request synthetic test data →</Link>
          </article>
        </section>
        <section className="mvp-panel">
          <h2>Know what to expect</h2>
          <p>
            Results are released after payment verification and review.
            Handwriting, faint marks, and complex grids may need manual
            transcription. Upload respondent pages in order; shuffled pages
            cannot reliably identify their respondent.
          </p>
          <p>
            You control the existing Google Form and authorize Google Apps
            Script yourself. We never request your Google password or claim to
            have verified form ownership.
          </p>
        </section>
      </main>
      <footer className="mvp-content">
        ScanToForms · Two services. Human review where it matters.
      </footer>
    </>
  );
}
