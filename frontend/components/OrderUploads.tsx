"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Order } from "@/lib/orders";
export default function OrderUploads({
  order,
  onChange,
}: {
  order: Order;
  onChange: () => Promise<void>;
}) {
  const [mode, setMode] = useState("BULK_ORDERED");
  const [files, setFiles] = useState<File[]>([]);
  const [start, setStart] = useState(1);
  const [respondent, setRespondent] = useState(1);
  const [slot, setSlot] = useState(1);
  const [kind, setKind] = useState(
    order.service_type === "SYNTHETIC_DATA" ? "TEMPLATE" : "RESPONSE",
  );
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const synthetic = order.service_type === "SYNTHETIC_DATA";
  async function upload(selected: File[], mobile = false) {
    setBusy(true);
    setError("");
    try {
      for (let i = 0; i < selected.length; i++) {
        const file = selected[i];
        const form = new FormData();
        form.append("upload", file);
        form.append("kind", kind);
        let sequence = respondent,
          page = slot;
        if (!mobile) {
          if (mode === "PDF_PER_RESPONSE") {
            sequence = start + i;
            page = 1;
          } else {
            const position = start - 1 + i;
            sequence = Math.floor(position / order.pages_per_respondent) + 1;
            page = (position % order.pages_per_respondent) + 1;
          }
        }
        const key =
          kind === "TEMPLATE"
            ? `template-${file.size}-${file.lastModified}-${file.name}`.slice(
                0,
                100,
              )
            : `respondent-${sequence}-${mode === "PDF_PER_RESPONSE" && !mobile ? "pdf" : `page-${page}`}`;
        form.append("upload_key", key);
        form.append("grouping_mode", mobile ? "MANUAL_RESPONSE" : mode);
        if (kind === "RESPONSE") {
          form.append("respondent_sequence", String(sequence));
          form.append("template_page_number", String(page));
        }
        setProgress(`Uploading ${i + 1}/${selected.length}: ${file.name}`);
        await api(`/orders/${order.reference}/uploads/`, {
          method: "POST",
          body: form,
        });
      }
      setFiles([]);
      setProgress("Upload saved. Check completeness below.");
      if (mobile && kind === "RESPONSE") {
        if (slot < order.pages_per_respondent) setSlot(slot + 1);
        else if (respondent < order.respondent_count) {
          setRespondent(respondent + 1);
          setSlot(1);
        }
      }
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "Upload failed."} Earlier successful uploads remain saved. Retry the same selection to resume, or choose a missing slot.`,
      );
    } finally {
      setBusy(false);
      await onChange();
    }
  }
  function move(index: number, direction: number) {
    setFiles((current) => {
      const next = [...current];
      [next[index], next[index + direction]] = [
        next[index + direction],
        next[index],
      ];
      return next;
    });
  }
  return (
    <section className="mvp-panel form-stack">
      <h2>
        2. Upload{" "}
        {synthetic ? "one blank questionnaire" : "questionnaire pages"}
      </h2>
      {synthetic ? (
        <p>
          Every file belongs to the same blank questionnaire. Five images mean
          five template pages, not five respondents.
        </p>
      ) : (
        <p>
          <strong>Upload respondents in order.</strong> Every{" "}
          {order.pages_per_respondent} consecutive images forms one respondent.
          Arbitrarily shuffled respondents cannot be identified automatically.
        </p>
      )}
      {!synthetic && (
        <label className="field">
          Upload purpose
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            disabled={busy}
          >
            <option value="RESPONSE">Completed respondent pages</option>
            <option value="TEMPLATE">
              Optional blank questionnaire template
            </option>
          </select>
        </label>
      )}
      {kind === "RESPONSE" && (
        <label className="field">
          Upload method
          <select
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              setFiles([]);
            }}
            disabled={busy}
          >
            <option value="BULK_ORDERED">Ordered page images</option>
            <option value="MANUAL_RESPONSE">
              Phone camera / exact page slots
            </option>
            <option value="PDF_PER_RESPONSE">
              One complete PDF per respondent
            </option>
          </select>
        </label>
      )}
      {kind === "RESPONSE" && mode === "MANUAL_RESPONSE" ? (
        <>
          <div className="form-row">
            <label className="field">
              Respondent
              <input
                type="number"
                min={1}
                max={order.respondent_count}
                value={respondent}
                onChange={(e) => setRespondent(Number(e.target.value))}
              />
            </label>
            <label className="field">
              Page
              <input
                type="number"
                min={1}
                max={order.pages_per_respondent}
                value={slot}
                onChange={(e) => setSlot(Number(e.target.value))}
              />
            </label>
          </div>
          <label className="capture-label">
            Capture respondent {respondent}, page {slot}
            <input
              aria-label="Capture questionnaire page"
              type="file"
              accept="image/jpeg,image/png"
              capture="environment"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void upload([file], true);
                e.target.value = "";
              }}
            />
          </label>
          <small>
            After saving, the next slot is selected automatically. Inspect the
            counts before payment.
          </small>
        </>
      ) : (
        <>
          {kind === "RESPONSE" && (
            <label className="field">
              {mode === "PDF_PER_RESPONSE"
                ? "Start at respondent number"
                : "Start at physical image number"}
              <input
                type="number"
                value={start}
                min={1}
                max={
                  mode === "PDF_PER_RESPONSE"
                    ? order.respondent_count
                    : order.expected_page_count
                }
                onChange={(e) => setStart(Number(e.target.value))}
              />
            </label>
          )}
          <label className="field">
            Choose{" "}
            {kind === "TEMPLATE"
              ? "PDF or questionnaire images"
              : mode === "PDF_PER_RESPONSE"
                ? "respondent PDFs"
                : "ordered JPG/PNG images"}
            <input
              type="file"
              multiple
              accept={
                kind === "TEMPLATE"
                  ? ".pdf,.png,.jpg,.jpeg"
                  : mode === "PDF_PER_RESPONSE"
                    ? ".pdf"
                    : ".png,.jpg,.jpeg"
              }
              disabled={busy}
              onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            />
          </label>
          {files.length > 0 && (
            <>
              <p>
                {files.length} file(s). Verify this order before uploading.
                Maximum 25 MB per file.
              </p>
              <ol className="file-order-list">
                {files.map((file, i) => (
                  <li key={`${file.name}-${i}`}>
                    <span>{file.name}</span>
                    <button
                      type="button"
                      disabled={busy || i === 0}
                      onClick={() => move(i, -1)}
                      aria-label={`Move ${file.name} up`}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      disabled={busy || i === files.length - 1}
                      onClick={() => move(i, 1)}
                      aria-label={`Move ${file.name} down`}
                    >
                      ↓
                    </button>
                  </li>
                ))}
              </ol>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => void upload(files)}
              >
                Upload selected files
              </button>
            </>
          )}
        </>
      )}
      {progress && <p role="status">{progress}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
