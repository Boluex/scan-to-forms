"use client";

import { CheckCircle2, ClipboardList, Clock3, FileText, ScanLine, UploadCloud } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api, download } from "@/lib/api";
import type { Batch, BillingSummary, Paginated, Questionnaire, QuestionnaireResponse } from "@/lib/types";

function statusClass(status: string) { return `status status-${status.toLowerCase()}`; }

export default function DashboardPage() {
  const [questionnaires, setQuestionnaires] = useState<Questionnaire[]>([]);
  const [batches, setBatches] = useState<Batch[]>([]);
  const [respondentResponses, setRespondentResponses] = useState<QuestionnaireResponse[]>([]);
  const [billing, setBilling] = useState<BillingSummary | null>(null);

  useEffect(() => {
    Promise.all([
      api<Paginated<Questionnaire>>("/questionnaires/"),
      api<Paginated<Batch>>("/response-batches/"),
      api<Paginated<QuestionnaireResponse>>("/responses/"),
      api<BillingSummary>("/billing/summary/"),
    ]).then(([q, b, r, account]) => { setQuestionnaires(q.results); setBatches(b.results); setRespondentResponses(r.results); setBilling(account); });
  }, []);

  const reviewCount = respondentResponses.filter((response) => ["INCOMPLETE", "NEEDS_REVIEW", "FAILED"].includes(response.status)).length;
  const responses = batches.reduce((total, batch) => total + batch.response_count, 0);

  async function exportBatch(batch: Batch, format: "csv" | "xlsx") {
    await download(`/exports/batches/${batch.id}/${format}/`, `${batch.name}.${format}`);
  }

  return (
    <div className="page-content">
      <header className="page-header"><div><h1>Your research, in motion.</h1><p>Track questionnaires from first upload to clean, confirmed data.</p></div><Link className="btn btn-dark" href="/dashboard/digitize"><UploadCloud size={16} /> New digitization</Link></header>
      <section className="metric-grid">
        <article className="metric-card"><div className="metric-top"><span>Questionnaires</span><span className="metric-icon"><ClipboardList size={15} /></span></div><strong>{questionnaires.length}</strong><small>Reusable structures</small></article>
        <article className="metric-card"><div className="metric-top"><span>Responses</span><span className="metric-icon"><FileText size={15} /></span></div><strong>{responses}</strong><small>Across all batches</small></article>
        <article className="metric-card"><div className="metric-top"><span>Needs review</span><span className="metric-icon"><Clock3 size={15} /></span></div><strong>{reviewCount}</strong><small>Uncertain documents</small></article>
        <article className="metric-card"><div className="metric-top"><span>Confirmed</span><span className="metric-icon"><CheckCircle2 size={15} /></span></div><strong>{batches.filter((batch) => batch.status === "COMPLETED").length}</strong><small>Completed batches</small></article>
      </section>
      <section className="content-grid">
        <div className="panel">
          <div className="panel-head"><h2>Recent respondents</h2><Link className="text-link" href="/dashboard/digitize">Upload more →</Link></div>
          {respondentResponses.length === 0 ? <div className="empty-state"><span className="empty-icon"><ScanLine size={22} /></span><h3>No questionnaire responses yet</h3><p>Upload completed pages to create your first respondent response.</p><Link className="btn btn-primary" href="/dashboard/digitize">Digitize now</Link></div> :
            <div className="activity-list">{respondentResponses.slice(0, 6).map((response) => <div className="activity-item" key={response.id}><span className="file-icon"><FileText size={16} /></span><div className="activity-copy"><strong>{response.respondent_reference || `Respondent #${response.sequence}`}</strong><span>{response.uploaded_page_count}/{response.expected_page_count} pages · {response.questionnaire_title}</span></div><span className={statusClass(response.status)}>{response.status.replaceAll("_", " ")}</span><Link className="mini-btn" href={`/dashboard/review/${response.id}`}>Review</Link></div>)}</div>}
        </div>
        <div className="panel">
          <div className="panel-head"><h2>Response batches</h2><span className="text-link">{batches.length} total</span></div>
          {batches.length === 0 ? <div className="empty-state"><span className="empty-icon"><FileText size={22} /></span><h3>No batches yet</h3><p>A batch groups completed copies of the same questionnaire.</p></div> :
            <div className="batch-list">{batches.slice(0, 5).map((batch) => <div className="batch-row" key={batch.id}><span className="file-icon"><ClipboardList size={15} /></span><div><h3>{batch.name}</h3><p>{batch.response_count} response{batch.response_count === 1 ? "" : "s"} · {batch.questionnaire_title}</p></div><div className="batch-actions"><button className="mini-btn" onClick={() => exportBatch(batch, "csv")}>CSV</button>{billing?.plan.has_xlsx && <button className="mini-btn" onClick={() => exportBatch(batch, "xlsx")}>XLSX</button>}</div></div>)}</div>}
        </div>
      </section>
    </div>
  );
}
