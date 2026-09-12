"use client";

import { AlertTriangle, Check, Clipboard, Download, FileCode2, Link2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useMemo, useState } from "react";

import { api, download } from "@/lib/api";
import type { AppsScriptJob, AppsScriptPreview, Batch, BillingSummary, BotRun, Paginated } from "@/lib/types";

type SourceType = "RESPONSE_BATCH" | "BOT_RUN";

function GoogleFormsWorkspace() {
  const query = useSearchParams();
  const [batches, setBatches] = useState<Batch[]>([]);
  const [botRuns, setBotRuns] = useState<BotRun[]>([]);
  const [jobs, setJobs] = useState<AppsScriptJob[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [source, setSource] = useState("");
  const [preview, setPreview] = useState<AppsScriptPreview | null>(null);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [formId, setFormId] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const requestedSource = query.get("source");
  const requestedId = query.get("id");

  function load() {
    return Promise.all([
      api<Paginated<Batch>>("/response-batches/"),
      api<Paginated<BotRun>>("/bot-lab/runs/"),
      api<Paginated<AppsScriptJob>>("/google-forms/scripts/"),
      api<BillingSummary>("/billing/summary/"),
    ]).then(([batchData, botData, scriptData, account]) => {
      setBatches(batchData.results);
      setBotRuns(botData.results.filter((run) => run.status === "COMPLETED"));
      setJobs(scriptData.results);
      setBilling(account);
    });
  }

  useEffect(() => { load().catch(() => setError("Google Forms tools could not be loaded.")); }, []);
  useEffect(() => {
    if (requestedSource && requestedId && !source) setSource(`${requestedSource}:${requestedId}`);
  }, [requestedSource, requestedId, source]);

  const selected = useMemo(() => {
    const separator = source.indexOf(":");
    if (separator < 0) return null;
    return { type: source.slice(0, separator) as SourceType, id: source.slice(separator + 1) };
  }, [source]);

  async function prepareMapping() {
    if (!selected) { setError("Choose a confirmed response batch or completed Bot Lab run."); return; }
    setBusy(true); setError(""); setMessage("");
    try {
      const data = await api<AppsScriptPreview>(`/google-forms/preview/?source_type=${selected.type}&source_id=${selected.id}`);
      setPreview(data);
      setMappings(Object.fromEntries(data.questions.map((question) => [question.key, question.suggested_google_item_title])));
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The mapping could not be prepared."); }
    finally { setBusy(false); }
  }

  async function generate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || !preview) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const job = await api<AppsScriptJob>("/google-forms/scripts/", {
        method: "POST",
        body: JSON.stringify({ source_type: selected.type, source_id: selected.id, form_id: formId, mappings }),
      });
      setJobs((current) => [job, ...current]);
      await navigator.clipboard.writeText(job.script);
      setMessage("Apps Script generated and copied. Run previewMapping() in Google Apps Script before submitting responses.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Apps Script could not be generated."); }
    finally { setBusy(false); }
  }

  async function copyScript(job: AppsScriptJob) {
    await navigator.clipboard.writeText(job.script);
    setMessage("Apps Script copied to your clipboard.");
  }

  if (!billing) return <div className="loading-screen"><div className="spinner" /></div>;
  if (!billing.plan.has_google_forms) return <div className="page-content"><div className="upgrade-panel"><Link2 size={31} /><h1>Google Forms is a Pro feature</h1><p>Upgrade to map confirmed or synthetic responses and generate resumable Apps Script code.</p><Link className="btn btn-primary" href="/dashboard/billing">View plans</Link></div></div>;

  return <div className="page-content">
    <header className="page-header"><div><h1>Google Forms Apps Script</h1><p>Map reviewed or synthetic data to Form items, then generate secure, resumable submission code.</p></div></header>
    <div className="synthetic-warning google-warning"><AlertTriangle size={19} /><div><strong>Review before submission</strong><span>The generated script submits real Google Form responses. Always run previewMapping() and verify item titles and types first.</span></div></div>
    {error && <div className="form-error" role="alert">{error}</div>}{message && <div className="form-success"><Check size={14} /> {message}</div>}
    <section className="google-grid">
      <form className="panel script-builder" onSubmit={generate}>
        <div className="panel-head"><h2>1. Choose and map data</h2></div>
        <div className="form-stack">
          <div className="field"><label htmlFor="script-source">Response source</label><select id="script-source" value={source} onChange={(event) => { setSource(event.target.value); setPreview(null); }} required><option value="">Choose a source</option><optgroup label="Confirmed response batches">{batches.map((batch) => <option key={batch.id} value={`RESPONSE_BATCH:${batch.id}`}>{batch.name} · {batch.response_count} total</option>)}</optgroup><optgroup label="Completed Bot Lab runs">{botRuns.map((run) => <option key={run.id} value={`BOT_RUN:${run.id}`}>{run.questionnaire_title} · {run.generated_responses} synthetic</option>)}</optgroup></select></div>
          <button className="btn btn-ghost" type="button" onClick={prepareMapping} disabled={!selected || busy}>Prepare question mapping</button>
          {preview && <><div className={`data-classification ${preview.source_type === "BOT_RUN" ? "synthetic" : "human"}`}>{preview.data_classification}<span>{preview.response_count} response{preview.response_count === 1 ? "" : "s"}</span></div><div className="field"><label htmlFor="form-id">Google Form ID or edit URL</label><input id="form-id" value={formId} onChange={(event) => setFormId(event.target.value)} placeholder="https://docs.google.com/forms/d/.../edit" required /><span className="form-note">You must own or have edit permission for this Google Form.</span></div><div className="mapping-list"><div className="mapping-head"><span>Questionnaire question</span><span>Exact Google Form item title</span></div>{preview.questions.map((question) => <label className="mapping-row" key={question.key}><span><strong>{question.text}</strong><small>{question.type.replaceAll("_", " ").toLowerCase()}</small></span><input value={mappings[question.key] ?? ""} onChange={(event) => setMappings((current) => ({ ...current, [question.key]: event.target.value }))} placeholder="Leave blank to skip" /></label>)}</div><button className="btn btn-primary btn-large" disabled={busy || !formId.trim()}><FileCode2 size={16} /> {busy ? "Generating…" : "Generate and copy Apps Script"}</button></>}
        </div>
      </form>
      <aside className="panel script-instructions"><div className="panel-head"><h2>2. Run it safely</h2></div><ol><li>Open <a href="https://script.google.com" target="_blank" rel="noreferrer">Google Apps Script</a> and create a project.</li><li>Paste the generated <code>.gs</code> code and save it.</li><li>Select and run <code>previewMapping</code>. Authorize Google Forms access when prompted.</li><li>Read the execution log and correct any missing or duplicate item titles.</li><li>Run <code>startSubmission</code>. It submits at most 40 records per execution.</li><li>For larger datasets, run <code>continueSubmission</code> until <code>submissionStatus</code> reports complete.</li></ol><p>The script records submitted ScanToForms IDs in Script Properties to protect normal reruns from duplicates.</p></aside>
    </section>
    <section className="panel script-history"><div className="panel-head"><h2>Generated scripts</h2><span className="text-link">{jobs.length} saved</span></div>{jobs.length === 0 ? <div className="empty-state"><span className="empty-icon"><FileCode2 size={22} /></span><h3>No Apps Script generated</h3><p>Your saved scripts will remain available for copying or download.</p></div> : <div className="activity-list">{jobs.map((job) => <div className="activity-item" key={job.id}><span className="file-icon"><FileCode2 size={16} /></span><div className="activity-copy"><strong>{job.source_name}</strong><span>{job.response_count} responses · {job.data_classification} · {new Date(job.created_at).toLocaleString()}</span></div><button className="mini-btn" onClick={() => copyScript(job)}><Clipboard size={12} /> Copy</button><button className="mini-btn" onClick={() => download(`/google-forms/scripts/${job.id}/download/`, `scan-to-forms-${job.id}.gs`)}><Download size={12} /> .gs</button></div>)}</div>}</section>
  </div>;
}

export default function GoogleFormsPage() { return <Suspense fallback={<div className="loading-screen"><div className="spinner" /></div>}><GoogleFormsWorkspace /></Suspense>; }
