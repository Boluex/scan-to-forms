"use client";

import { ArrowLeft, ClipboardList } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Questionnaire } from "@/lib/types";

export default function QuestionnaireDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [item, setItem] = useState<Questionnaire | null>(null);
  useEffect(() => { api<Questionnaire>(`/questionnaires/${id}/`).then(setItem); }, [id]);
  if (!item) return <div className="loading-screen"><div className="spinner" /></div>;
  const version = item.latest_version;
  if (!version) return <div className="page-content"><div className="empty-state"><span className="empty-icon"><ClipboardList size={22} /></span><h3>No questionnaire version yet</h3><p>Create a quick setup or upload a blank questionnaire to begin.</p></div></div>;
  return <div className="page-content"><header className="page-header"><div><Link className="text-link" href="/dashboard/questionnaires"><ArrowLeft size={13} /> All questionnaires</Link><h1 style={{ marginTop: 12 }}>{item.title}</h1><p>{item.description || "No description added."}</p></div><span className={`status status-${item.status.toLowerCase()}`}>{item.status}</span></header><section className="panel"><div className="panel-head"><h2>Version {version.version_number} question structure</h2><span className="text-link">{version.questions.length} questions · {version.expected_page_count} page{version.expected_page_count === 1 ? "" : "s"} per response</span></div>{version.template_pages.length > 0 && <div className="template-page-strip">{version.template_pages.map((page) => <span key={page.id}>Template page {page.page_number} · {page.anchors.length} anchors</span>)}</div>}{version.questions.length === 0 ? <div className="empty-state"><span className="empty-icon"><ClipboardList size={22} /></span><h3>No questions detected</h3><p>Use the API or Django admin to refine this draft, or create a new quick-setup questionnaire.</p></div> : <div className="batch-list">{version.questions.map((question) => <div className="batch-row" key={question.id}><span className="answer-number">{question.position}</span><div><h3>{question.text}</h3><p>{question.type.replaceAll("_", " ").toLowerCase()} · {question.required ? "required" : "optional"} · {question.template_page_number ? `page ${question.template_page_number}` : "page not assigned"}</p></div></div>)}</div>}</section></div>;
}
