import { ArrowRight, Check, FileCheck2, ScanLine, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";

import PricingPreview from "./components/PricingPreview";

const steps = [
  { number: "01", title: "Upload", body: "Add a PDF, scan, or phone photo of your completed questionnaire." },
  { number: "02", title: "Extract", body: "Local AI reads questions, marks, and written answers with confidence scores." },
  { number: "03", title: "Review", body: "Check uncertain answers beside the original document. You stay in control." },
  { number: "04", title: "Export", body: "Download clean CSV or Excel data—one respondent per row." },
];

export default function LandingPage() {
  return (
    <main className="landing">
      <nav className="public-nav shell">
        <Link className="brand" href="/">
          <span className="brand-mark"><ScanLine size={20} /></span>
          <span>ScanToForms</span>
        </Link>
        <div className="nav-links">
          <a href="#how">How it works</a>
          <a href="#trust">Why it works</a>
          <a href="#pricing">Pricing</a>
        </div>
        <div className="nav-actions">
          <Link className="btn btn-ghost" href="/login">Log in</Link>
          <Link className="btn btn-dark" href="/register">Start free <ArrowRight size={16} /></Link>
        </div>
      </nav>

      <section className="hero shell">
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={14} /> Made for real research work</div>
          <h1>Stop typing.<br /><span>Start scanning.</span></h1>
          <p className="hero-lede">Turn piles of completed paper questionnaires into clean, structured data—without spending nights on manual entry.</p>
          <div className="hero-actions">
            <Link className="btn btn-primary btn-large" href="/register">Digitize your first form <ArrowRight size={18} /></Link>
            <span className="free-note"><Check size={15} /> Free to get started</span>
          </div>
        </div>
        <div className="hero-visual" aria-label="Questionnaire extraction preview">
          <div className="scan-glow" />
          <div className="paper-card">
            <div className="paper-head"><span /> <span /></div>
            <div className="paper-line long" />
            <div className="paper-line medium" />
            <div className="paper-question">
              <small>Q1</small><div><b>What is your department?</b><span className="handwriting">Computer Science</span></div>
            </div>
            <div className="paper-question">
              <small>Q2</small><div><b>How satisfied are you?</b><span className="choice-row">○ 1 &nbsp; ○ 2 &nbsp; ○ 3 &nbsp; ● 4 &nbsp; ○ 5</span></div>
            </div>
          </div>
          <div className="scan-beam" />
          <div className="result-card">
            <div className="result-top"><span className="status-dot" /> Extracted response <span className="confidence-pill">94% confidence</span></div>
            <div className="result-row"><span>Department</span><strong>Computer Science</strong></div>
            <div className="result-row"><span>Satisfaction</span><strong>4 / 5</strong></div>
            <div className="result-ready"><FileCheck2 size={17} /> Ready to review</div>
          </div>
        </div>
      </section>

      <section className="proof-strip">
        <div className="shell proof-inner">
          <p>Built for the forms researchers actually use</p>
          <span>☑ Checkboxes</span><span>◉ Multiple choice</span><span>✎ Handwriting</span><span>▦ Likert grids</span><span>▤ Multi-page PDFs</span>
        </div>
      </section>

      <section className="how shell" id="how">
        <div className="section-kicker">The simple path</div>
        <div className="section-heading"><h2>From paper stack to spreadsheet.</h2><p>AI handles the repetitive work. You make the final call on anything uncertain.</p></div>
        <div className="steps-grid">
          {steps.map((step) => <article className="step-card" key={step.number}><span>{step.number}</span><h3>{step.title}</h3><p>{step.body}</p></article>)}
        </div>
      </section>

      <section className="trust shell" id="trust">
        <div className="trust-card">
          <div className="trust-icon"><ShieldCheck size={30} /></div>
          <div><div className="section-kicker">Confidence, not guesswork</div><h2>AI that shows its uncertainty.</h2><p>Every answer includes a confidence score. Low-confidence handwriting and ambiguous marks are surfaced first, beside the source document, so your final dataset is defensible.</p></div>
          <ul><li><Check size={17} /> Human review is always available</li><li><Check size={17} /> Your files stay private</li><li><Check size={17} /> No questionnaire data used for training</li></ul>
        </div>
      </section>

      <PricingPreview />

      <section className="cta shell">
        <div><span className="section-kicker">Your backlog can wait no longer</span><h2>Give yourself the hours back.</h2><p>Start with one questionnaire. No card required.</p></div>
        <Link className="btn btn-primary btn-large" href="/register">Start digitizing free <ArrowRight size={18} /></Link>
      </section>

      <footer className="shell footer"><div className="brand"><span className="brand-mark"><ScanLine size={18} /></span> ScanToForms</div><p>Research data entry, made humane.</p><span>© 2026 ScanToForms</span></footer>
    </main>
  );
}
