"use client";

import { AlertTriangle, Bot, Download, ExternalLink, Play } from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { api, download } from "@/lib/api";
import type { BillingSummary, BotRun, Paginated, Questionnaire } from "@/lib/types";

export default function BotLabPage() {
  const [questionnaires, setQuestionnaires] = useState<Questionnaire[]>([]);
  const [runs, setRuns] = useState<BotRun[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function load() {
    return Promise.all([
      api<Paginated<Questionnaire>>("/questionnaires/"),
      api<Paginated<BotRun>>("/bot-lab/runs/"),
      api<BillingSummary>("/billing/summary/"),
    ]).then(([q, r, account]) => { setQuestionnaires(q.results.filter((item) => item.latest_version)); setRuns(r.results); setBilling(account); });
  }
  useEffect(() => { load().catch(() => setError("Bot Lab could not be loaded.")); }, []);
  useEffect(() => {
    if (!runs.some((run) => ["QUEUED", "PROCESSING"].includes(run.status))) return;
    const timer = window.setInterval(() => { load(); }, 2500);
    return () => window.clearInterval(timer);
  }, [runs]);

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    const form = new FormData(event.currentTarget);
    try {
      await api<BotRun>("/bot-lab/runs/", { method: "POST", body: JSON.stringify({ questionnaire_version: form.get("questionnaire_version"), requested_responses: Number(form.get("requested_responses")) }) });
      await load();
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The Bot Lab run could not be created."); }
    finally { setBusy(false); }
  }

  if (!billing) return <div className="loading-screen"><div className="spinner" /></div>;
  const canRun = billing.usage.bot_lab_runs_used < billing.usage.bot_lab_runs_included;
  const maxResponses = billing.plan.code === "ORGANIZATION" ? 1000 : billing.plan.code === "RESEARCHER" ? 500 : 100;
  return <div className="page-content">
    <header className="page-header"><div><h1>Bot Lab</h1><p>Generate questionnaire-safe test data without pretending bots are human respondents.</p></div><Link className="btn btn-dark" href="/dashboard/google-forms"><ExternalLink size={15} /> Google Forms scripts</Link></header>
    <div className="synthetic-warning"><AlertTriangle size={19} /><div><strong>SYNTHETIC DATA — NOT VALID HUMAN RESEARCH RESPONSES</strong><span>Use generated datasets only for forms, exports, analytics and pipeline testing.</span></div></div>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="content-grid bot-grid">
      <form className="panel bot-form" onSubmit={createRun}><div className="panel-head"><h2>New synthetic dataset</h2><span className="nav-badge">{billing.usage.bot_lab_runs_used}/{billing.usage.bot_lab_runs_included} used</span></div><div className="form-stack">
        <div className="field"><label htmlFor="questionnaire_version">Questionnaire</label><select id="questionnaire_version" name="questionnaire_version" required><option value="">Choose a questionnaire</option>{questionnaires.map((item) => <option key={item.id} value={item.latest_version?.id}>{item.title}</option>)}</select></div>
        <div className="field"><label htmlFor="requested_responses">Synthetic responses</label><input id="requested_responses" name="requested_responses" type="number" min="1" max={maxResponses} defaultValue={Math.min(50, maxResponses)} required /><span className="form-note">Up to {maxResponses.toLocaleString()} responses in this run.</span></div>
        <button className="btn btn-primary" disabled={!canRun || busy || questionnaires.length === 0}><Play size={15} /> {busy ? "Starting…" : "Generate dataset"}</button>
        {!canRun && <p className="form-note">Your monthly Bot Lab allowance is used. Contact <a href={`mailto:${billing.admin_contact_email}?subject=More Bot Lab runs`}>the administrator</a> for more.</p>}
      </div></form>
      <section className="panel"><div className="panel-head"><h2>Recent Bot Lab runs</h2></div>{runs.length === 0 ? <div className="empty-state"><span className="empty-icon"><Bot size={22} /></span><h3>No synthetic datasets yet</h3><p>Your completed runs will be clearly labeled and downloadable here.</p></div> : <div className="activity-list">{runs.map((run) => <div className="activity-item" key={run.id}><span className="file-icon"><Bot size={16} /></span><div className="activity-copy"><strong>{run.questionnaire_title}</strong><span>{run.generated_responses || run.requested_responses} synthetic responses · {new Date(run.created_at).toLocaleString()}</span></div><span className={`status status-${run.status.toLowerCase()}`}>{run.status}</span>{run.download_url && <><button className="mini-btn" onClick={() => download(`/bot-lab/runs/${run.id}/csv/`, `synthetic-${run.id}.csv`)}><Download size={12} /> CSV</button><Link className="mini-btn" href={`/dashboard/google-forms?source=BOT_RUN&id=${run.id}`}>Apps Script</Link></>}</div>)}</div>}</section>
    </section>
  </div>;
}
