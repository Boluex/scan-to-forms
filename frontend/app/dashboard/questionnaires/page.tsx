"use client";

import { ClipboardList, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Paginated, Questionnaire } from "@/lib/types";

export default function QuestionnairesPage() {
  const [items, setItems] = useState<Questionnaire[] | null>(null);
  useEffect(() => { api<Paginated<Questionnaire>>("/questionnaires/").then((data) => setItems(data.results)); }, []);
  return <div className="page-content"><header className="page-header"><div><h1>My questionnaires</h1><p>Reusable, versioned structures for every response batch.</p></div><Link className="btn btn-primary" href="/dashboard/digitize"><Plus size={16} /> New questionnaire</Link></header><section className="panel">{items === null ? <div className="loading-screen"><div className="spinner" /></div> : items.length === 0 ? <div className="empty-state"><span className="empty-icon"><ClipboardList size={22} /></span><h3>No questionnaire structures yet</h3><p>Create one from a clear blank scan or enter its questions directly.</p><Link className="btn btn-primary" href="/dashboard/digitize">Create one</Link></div> : <div className="batch-list">{items.map((item) => <Link className="batch-row" href={`/dashboard/questionnaires/${item.id}`} key={item.id}><span className="file-icon"><ClipboardList size={15} /></span><div><h3>{item.title}</h3><p>Version {item.latest_version?.version_number ?? "—"} · {item.latest_version?.questions.length ?? 0} questions · {item.latest_version?.expected_page_count ?? 1} page(s)/respondent · {new Date(item.created_at).toLocaleDateString()}</p></div><span className={`status status-${item.status.toLowerCase()}`}>{item.status}</span></Link>)}</div>}</section></div>;
}
