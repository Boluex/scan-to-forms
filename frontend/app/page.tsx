import Link from "next/link";
import {
  ArrowRight,
  ScanLine,
  Check,
  FileText,
  ShieldCheck,
  FlaskConical,
  Bell,
} from "lucide-react";
export default function Home() {
  return (
    <div className="public-site">
      <header className="public-header">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <ScanLine size={21} />
          </span>
          ScanToForms
        </Link>
        <nav aria-label="Main navigation">
          <a href="#how-it-works">How it works</a>
          <a href="#services">Our services</a>
          <Link href="/login">Log in</Link>
        </nav>
        <Link href="/register" className="btn btn-primary">
          Get started <ArrowRight size={16} />
        </Link>
      </header>
      <main>
        <section className="home-hero">
          <div>
            <p className="section-kicker">A clearer path from paper to data</p>
            <h1>
              Less data entry.
              <br />
              <span>More discovery.</span>
            </h1>
            <p className="home-lede">
              Turn your completed questionnaires into organised, reviewed
              responses. One workspace to upload, track, and collect your
              results.
            </p>
            <div className="button-row">
              <Link href="/digitize" className="btn btn-primary btn-large">
                Digitize my questionnaires <ArrowRight size={18} />
              </Link>
              <a href="#how-it-works" className="quiet-link">
                See how it works
              </a>
            </div>
            <p className="hero-footnote">
              <ShieldCheck size={16} /> Private uploads. Human review. Your
              research.
            </p>
          </div>
          <div
            className="research-preview"
            aria-label="Illustration of the questionnaire review workflow"
          >
            <div className="preview-caption">
              <span className="tiny-dot" /> YOUR RESEARCH WORKSPACE{" "}
              <span>Preview</span>
            </div>
            <div className="preview-document">
              <div className="preview-file">
                <FileText size={24} />
                <div>
                  <strong>Final year research</strong>
                  <small>Completed questionnaires</small>
                </div>
                <span className="file-extension">PDF</span>
              </div>
              <div className="preview-rule" />
              <div className="sample-answer">
                <span>01</span>
                <div>
                  <small>Department</small>
                  <strong>Engineering</strong>
                </div>
                <Check size={18} />
              </div>
              <div className="sample-answer">
                <span>02</span>
                <div>
                  <small>Level of study</small>
                  <strong>Undergraduate</strong>
                </div>
                <Check size={18} />
              </div>
              <div className="sample-answer">
                <span>03</span>
                <div>
                  <small>Response status</small>
                  <strong>Reviewed and organised</strong>
                </div>
                <Check size={18} />
              </div>
            </div>
            <div className="preview-progress">
              <span>
                <Check size={14} /> Upload
              </span>
              <i />
              <span>
                <Check size={14} /> Review
              </span>
              <i />
              <strong>Results</strong>
            </div>
            <div className="preview-notice">
              <Bell size={19} />
              <div>
                <strong>Your results, ready when you are.</strong>
                <small>Get an update in your notification inbox.</small>
              </div>
            </div>
          </div>
        </section>
        <section id="how-it-works" className="home-section">
          <div className="section-intro">
            <p className="section-kicker">Simple from the start</p>
            <h2>
              Your next chapter starts
              <br />
              with a clearer workflow.
            </h2>
            <p>Four steps from a stack of paper to data you can use.</p>
          </div>
          <div className="workflow-grid">
            {[
              [
                "01",
                "Upload your pages",
                "Add one PDF per respondent or ordered page images. Keep multi-page responses together.",
              ],
              [
                "02",
                "Confirm your order",
                "Check your page count and pricing, then submit your bank transfer for verification.",
              ],
              [
                "03",
                "We process and review",
                "An operator checks the extracted answers and resolves uncertain pages.",
              ],
              [
                "04",
                "Collect your results",
                "Receive an update, download your data, and use your Apps Script with your Google Form.",
              ],
            ].map(([number, title, text]) => (
              <article key={number}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{text}</p>
              </article>
            ))}
          </div>
        </section>
        <section id="services" className="home-section service-section">
          <div className="section-intro">
            <p className="section-kicker">Choose your starting point</p>
            <h2>Two ways to move forward.</h2>
          </div>
          <div className="service-grid">
            <article>
              <div className="section-icon">
                <ScanLine />
              </div>
              <h3>Questionnaire digitization</h3>
              <p>
                For completed paper responses. Upload, track progress, and
                receive reviewed data for your research workflow.
              </p>
              <Link href="/digitize">
                Start digitizing <ArrowRight size={17} />
              </Link>
            </article>
            <article>
              <div className="section-icon">
                <FlaskConical />
              </div>
              <h3>Synthetic test data</h3>
              <p>
                For testing forms and analysis tools. Get clearly labelled
                sample data. Synthetic data does not represent real research
                respondents.
              </p>
              <Link href="/synthetic">
                Create test data <ArrowRight size={17} />
              </Link>
            </article>
          </div>
        </section>
        <section className="home-callout">
          <div>
            <p className="section-kicker">
              Make room for the work that matters
            </p>
            <h2>
              Your research deserves
              <br />a little less busywork.
            </h2>
            <p>
              Handwriting and complex layouts may need manual transcription.
              <br />
              Every result is released after payment verification and review.
            </p>
          </div>
          <Link href="/register" className="btn btn-primary btn-large">
            Create your workspace <ArrowRight size={18} />
          </Link>
        </section>
      </main>
      <footer className="public-footer">
        <Link href="/" className="brand">
          <ScanLine size={21} />
          ScanToForms
        </Link>
        <p>Paper questionnaires. Clearer possibilities.</p>
        <Link href="/login">
          Open workspace <ArrowRight size={14} />
        </Link>
      </footer>
    </div>
  );
}
