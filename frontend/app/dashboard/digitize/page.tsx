"use client";

import { Check, FileImage, FileText, Plus, ScanLine, Trash2, UploadCloud, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { DragEvent, FormEvent, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { Batch, BulkPreparation, Document, Questionnaire, QuestionnaireResponse, Version } from "@/lib/types";

type SetupMode = "scan" | "manual";
type UploadMode = "PDF_PER_RESPONSE" | "BULK_ORDERED" | "MANUAL_RESPONSE";
type ManualRespondent = Array<File | null>;

function FileDrop({ files, setFiles, single = false, label, accept = ".pdf,.jpg,.jpeg,.png" }: { files: File[]; setFiles: (files: File[]) => void; single?: boolean; label: string; accept?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const add = (incoming: File[]) => setFiles((single ? incoming.slice(0, 1) : [...files, ...incoming]).filter((file, index, all) => all.findIndex((candidate) => candidate.name === file.name && candidate.size === file.size) === index));
  function drop(event: DragEvent) { event.preventDefault(); setDragging(false); add(Array.from(event.dataTransfer.files)); }
  return <><button type="button" className={`dropzone ${dragging ? "dragging" : ""}`} onClick={() => input.current?.click()} onDragOver={(event) => { event.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={drop}><span className="drop-icon"><UploadCloud size={22} /></span><strong>{label}</strong><span>PDF, JPG or PNG · up to 25 MB each</span><input ref={input} type="file" accept={accept} multiple={!single} onChange={(event) => add(Array.from(event.target.files ?? []))} /></button>{files.length > 0 && <div className="file-chips">{files.map((file) => <span className="file-chip" key={`${file.name}-${file.size}`}><FileImage size={12} /> {file.name}<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setFiles(files.filter((candidate) => candidate !== file))}><X size={11} /></button></span>)}</div>}</>;
}

function PageFile({ pageNumber, file, setFile }: { pageNumber: number; file: File | null; setFile: (file: File | null) => void }) {
  const input = useRef<HTMLInputElement>(null);
  return <div className={`page-file-slot ${file ? "filled" : ""}`}><div><strong>Page {pageNumber}</strong><span>{file ? file.name : "Missing until uploaded"}</span></div><button type="button" className="mini-btn" onClick={() => file ? setFile(null) : input.current?.click()}>{file ? <><X size={12} /> Remove</> : <><UploadCloud size={12} /> Choose image</>}</button><input ref={input} hidden type="file" accept=".jpg,.jpeg,.png" onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></div>;
}

async function uploadDocument(file: File, fields: Record<string, string>) {
  const form = new FormData();
  form.append("upload", file);
  Object.entries(fields).forEach(([key, value]) => form.append(key, value));
  return api<Document>("/documents/", { method: "POST", body: form });
}

async function waitForDocument(id: string) {
  for (let attempt = 0; attempt < 45; attempt += 1) {
    const document = await api<Document>(`/documents/${id}/`);
    if (["NEEDS_REVIEW", "COMPLETED", "FAILED"].includes(document.status)) return document;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error("Processing is taking longer than expected. It will continue in the background.");
}

export default function DigitizePage() {
  const router = useRouter();
  const [mode, setMode] = useState<SetupMode>("manual");
  const [uploadMode, setUploadMode] = useState<UploadMode>("PDF_PER_RESPONSE");
  const [expectedPages, setExpectedPages] = useState(1);
  const [templateFiles, setTemplateFiles] = useState<File[]>([]);
  const [responseFiles, setResponseFiles] = useState<File[]>([]);
  const [manualRespondents, setManualRespondents] = useState<ManualRespondent[]>([[null]]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");

  function changeExpectedPages(value: number) {
    const next = Math.min(100, Math.max(1, value || 1));
    setExpectedPages(next);
    setManualRespondents((groups) => groups.map((group) => Array.from({ length: next }, (_, index) => group[index] ?? null)));
  }

  function updateManualPage(respondentIndex: number, pageIndex: number, file: File | null) {
    setManualRespondents((groups) => groups.map((group, index) => index === respondentIndex ? group.map((current, slot) => slot === pageIndex ? file : current) : group));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const title = String(form.get("title") ?? "").trim();
    const batchName = String(form.get("batchName") ?? "").trim();
    const lines = String(form.get("questions") ?? "").split("\n").map((line) => line.trim()).filter(Boolean);
    const manualFileCount = manualRespondents.flat().filter(Boolean).length;
    const responseFileCount = uploadMode === "MANUAL_RESPONSE" ? manualFileCount : responseFiles.length;
    if (!title || !batchName || responseFileCount === 0) { setError("Add a title, batch name, and at least one completed response page."); return; }
    if (mode === "manual" && lines.length === 0) { setError("Enter at least one question for quick setup."); return; }
    if (mode === "scan" && templateFiles.length === 0) { setError("Add a blank questionnaire so the page structure can be detected."); return; }
    if (uploadMode === "PDF_PER_RESPONSE" && responseFiles.some((file) => !file.name.toLowerCase().endsWith(".pdf"))) { setError("PDF-per-respondent mode accepts one PDF file for each respondent."); return; }
    if (uploadMode === "BULK_ORDERED" && responseFiles.some((file) => file.name.toLowerCase().endsWith(".pdf"))) { setError("Bulk ordered mode accepts JPG/JPEG/PNG page images only."); return; }

    setBusy(true); setError(""); setProgress(8); setMessage("Creating questionnaire workspace…");
    try {
      const questionnaire = await api<Questionnaire>("/questionnaires/", { method: "POST", body: JSON.stringify({ title, description: form.get("description") ?? "" }) });
      let version: Version;
      if (mode === "manual") {
        setMessage("Saving question and page structure…"); setProgress(20);
        version = await api<Version>(`/questionnaires/${questionnaire.id}/versions/`, {
          method: "POST",
          body: JSON.stringify({ expected_page_count: expectedPages, parse_status: "VALID", parser_version: "manual-2", questions: lines.map((text, index) => ({ key: `q${index + 1}`, position: index + 1, text, type: "SHORT_TEXT", required: false, template_page_number: null, options: [] })) }),
        });
      } else {
        setMessage("Reading the blank questionnaire and its pages…"); setProgress(15);
        const template = await uploadDocument(templateFiles[0], { document_type: "TEMPLATE", questionnaire: questionnaire.id, grouping_mode: "TEMPLATE" });
        const processed = await waitForDocument(template.id);
        if (processed.status === "FAILED") throw new Error(processed.ocr_job?.error_message || "The blank questionnaire could not be processed.");
        const refreshed = await api<Questionnaire>(`/questionnaires/${questionnaire.id}/`);
        if (!refreshed.latest_version?.questions?.length) throw new Error("No questions were confidently detected. The draft was saved; retry with a clearer scan or use quick setup.");
        version = refreshed.latest_version;
      }

      setMessage("Creating response batch…"); setProgress(35);
      const batch = await api<Batch>("/response-batches/", { method: "POST", body: JSON.stringify({ questionnaire_version: version.id, name: batchName }) });
      let completedUploads = 0;
      const updateUploadProgress = () => { completedUploads += 1; setProgress(40 + Math.round((completedUploads / responseFileCount) * 55)); };

      if (uploadMode === "PDF_PER_RESPONSE") {
        for (let index = 0; index < responseFiles.length; index += 1) {
          setMessage(`Uploading respondent PDF ${index + 1} of ${responseFiles.length}…`);
          await uploadDocument(responseFiles[index], { document_type: "RESPONSE", batch: batch.id, grouping_mode: "PDF_PER_RESPONSE" });
          updateUploadProgress();
        }
      } else if (uploadMode === "BULK_ORDERED") {
        const prepared = await api<BulkPreparation>(`/response-batches/${batch.id}/prepare-bulk/`, { method: "POST", body: JSON.stringify({ file_count: responseFiles.length }) });
        for (const assignment of prepared.assignments) {
          setMessage(`Uploading page image ${assignment.upload_index} of ${responseFiles.length}…`);
          await uploadDocument(responseFiles[assignment.upload_index - 1], {
            document_type: "RESPONSE",
            batch: batch.id,
            response: assignment.response_id,
            grouping_mode: "BULK_ORDERED",
            template_page_number: String(assignment.template_page_number),
          });
          updateUploadProgress();
        }
      } else {
        for (let respondentIndex = 0; respondentIndex < manualRespondents.length; respondentIndex += 1) {
          const pages = manualRespondents[respondentIndex];
          if (!pages.some(Boolean)) continue;
          const response = await api<QuestionnaireResponse>("/responses/", { method: "POST", body: JSON.stringify({ batch: batch.id, respondent_reference: `R-${String(respondentIndex + 1).padStart(4, "0")}` }) });
          for (let pageIndex = 0; pageIndex < pages.length; pageIndex += 1) {
            const file = pages[pageIndex];
            if (!file) continue;
            setMessage(`Uploading respondent ${respondentIndex + 1}, page ${pageIndex + 1}…`);
            await uploadDocument(file, { document_type: "RESPONSE", batch: batch.id, response: response.id, grouping_mode: "MANUAL_RESPONSE", template_page_number: String(pageIndex + 1) });
            updateUploadProgress();
          }
        }
      }
      setMessage("Pages grouped and queued. Incomplete or uncertain respondents will be flagged for review."); setProgress(100);
      setTimeout(() => router.push("/dashboard"), 1000);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Digitization could not be started.");
      setBusy(false);
    }
  }

  const steps = [{ title: "Structure", note: "Define questions and pages" }, { title: "Group", note: "Pages become respondents" }, { title: "Process", note: "OCR every physical page" }, { title: "Review", note: "Confirm one complete response" }];
  return <div className="page-content"><header className="page-header"><div><h1>Digitize a questionnaire</h1><p>Define one reusable questionnaire, then group completed pages into respondent responses.</p></div></header><div className="wizard"><aside className="wizard-rail">{steps.map((step, index) => <div className={`wizard-step ${index === 0 ? "active" : ""}`} key={step.title}><span className="step-number">{index + 1}</span><div><strong>{step.title}</strong><p>{step.note}</p></div></div>)}</aside><form className="wizard-panel" onSubmit={submit}><h2>Set up this response batch</h2><p>One respondent may contain several physical pages. OCR pages are charged separately, but exports and Google Forms use one logical response per respondent.</p>{error && <div className="form-error" role="alert">{error}</div>}{busy ? <div className="progress-box"><strong>{progress === 100 ? <Check size={18} /> : <ScanLine size={18} />} {message}</strong><div className="progress-track"><div className="progress-fill" style={{ width: `${progress}%` }} /></div><span className="form-note">You can leave after every upload has been queued.</span></div> : <><div className="form-row"><div className="field"><label htmlFor="title">Questionnaire title</label><input id="title" name="title" placeholder="Student housing survey" required /></div><div className="field"><label htmlFor="batchName">Batch name</label><input id="batchName" name="batchName" placeholder="August physical responses" required /></div></div><div className="field"><label htmlFor="description">Description <span className="form-note">(optional)</span></label><input id="description" name="description" placeholder="Internal context for this project" /></div><div className="form-row"><div className="field"><label htmlFor="expectedPages">Pages in one completed questionnaire</label><input id="expectedPages" type="number" min="1" max="100" value={expectedPages} onChange={(event) => changeExpectedPages(Number(event.target.value))} required /><span className="form-note">Example: enter 4 when every respondent should have pages 1–4.</span></div></div><div className="choice-tabs"><button type="button" className={`choice-tab ${mode === "manual" ? "active" : ""}`} onClick={() => setMode("manual")}><FileText size={13} /> Quick question setup</button><button type="button" className={`choice-tab ${mode === "scan" ? "active" : ""}`} onClick={() => setMode("scan")}><ScanLine size={13} /> Detect from blank scan</button></div>{mode === "manual" ? <div className="field section-gap"><label htmlFor="questions">Questions — one per line</label><textarea id="questions" name="questions" placeholder={"What is your department?\nWhat is your age?\nHow satisfied are you with the service?"} /><span className="form-note">Question types and page assignments can be refined later.</span></div> : <div className="section-gap"><FileDrop files={templateFiles} setFiles={setTemplateFiles} single label="Drop one blank questionnaire PDF/image here" /></div>}<section className="upload-mode-section"><h3>How are completed responses organized?</h3><div className="upload-mode-grid"><button type="button" className={uploadMode === "PDF_PER_RESPONSE" ? "active" : ""} onClick={() => setUploadMode("PDF_PER_RESPONSE")}><strong>One PDF per respondent</strong><span>Each multi-page PDF automatically becomes one response.</span></button><button type="button" className={uploadMode === "BULK_ORDERED" ? "active" : ""} onClick={() => setUploadMode("BULK_ORDERED")}><strong>Bulk ordered images</strong><span>Every {expectedPages} consecutive images provisionally form one response.</span></button><button type="button" className={uploadMode === "MANUAL_RESPONSE" ? "active" : ""} onClick={() => setUploadMode("MANUAL_RESPONSE")}><strong>Manual respondents</strong><span>Choose the exact page slots for each respondent.</span></button></div></section>{uploadMode === "PDF_PER_RESPONSE" && <div className="section-gap"><FileDrop files={responseFiles} setFiles={setResponseFiles} label="Drop one completed PDF per respondent" accept=".pdf" /></div>}{uploadMode === "BULK_ORDERED" && <div className="section-gap"><FileDrop files={responseFiles} setFiles={setResponseFiles} label="Drop page images in respondent order" accept=".jpg,.jpeg,.png" /><p className="form-note">The initial grouping uses upload order. OCR page markers and template-text similarity validate or correct page numbers afterward; uncertain assignments remain reviewable.</p></div>}{uploadMode === "MANUAL_RESPONSE" && <div className="manual-respondents">{manualRespondents.map((pages, respondentIndex) => <section className="manual-respondent" key={respondentIndex}><header><div><strong>Respondent #{respondentIndex + 1}</strong><span>{pages.filter(Boolean).length}/{expectedPages} pages attached</span></div>{manualRespondents.length > 1 && <button type="button" className="mini-btn" onClick={() => setManualRespondents((groups) => groups.filter((_, index) => index !== respondentIndex))}><Trash2 size={12} /> Remove</button>}</header>{pages.map((file, pageIndex) => <PageFile key={pageIndex} pageNumber={pageIndex + 1} file={file} setFile={(next) => updateManualPage(respondentIndex, pageIndex, next)} />)}</section>)}<button type="button" className="btn btn-ghost" onClick={() => setManualRespondents((groups) => [...groups, Array(expectedPages).fill(null)])}><Plus size={14} /> Add another respondent</button></div>}<div className="wizard-actions"><button className="btn btn-ghost" type="button" onClick={() => history.back()}>Cancel</button><button className="btn btn-primary btn-large" type="submit"><UploadCloud size={17} /> Group and digitize</button></div></>}</form></div></div>;
}
