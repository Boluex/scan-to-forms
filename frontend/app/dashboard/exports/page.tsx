"use client";

import { FileSpreadsheet } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Paginated } from "@/lib/types";

type Export = { id: string; batch_name: string; format: string; status: string; response_count: number; created_at: string };

export default function ExportsPage() {
  const [exports, setExports] = useState<Export[] | null>(null);
  useEffect(() => { api<Paginated<Export>>("/exports/").then((data) => setExports(data.results)); }, []);
  return <div className="page-content"><header className="page-header"><div><h1>Export history</h1><p>Audit the datasets created from your response batches.</p></div></header><section className="panel">{exports === null ? <div className="loading-screen"><div className="spinner" /></div> : exports.length === 0 ? <div className="empty-state"><span className="empty-icon"><FileSpreadsheet size={22} /></span><h3>No exports yet</h3><p>Use the CSV or XLSX controls on a dashboard response batch.</p></div> : <div className="batch-list">{exports.map((item) => <div className="batch-row" key={item.id}><span className="file-icon"><FileSpreadsheet size={15} /></span><div><h3>{item.batch_name}.{item.format.toLowerCase()}</h3><p>{item.response_count} responses · {new Date(item.created_at).toLocaleString()}</p></div><span className={`status status-${item.status.toLowerCase()}`}>{item.status}</span></div>)}</div>}</section></div>;
}

