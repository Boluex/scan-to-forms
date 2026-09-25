"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Order } from "@/lib/orders";
import { Version, Paginated } from "@/lib/types";
type Detail = {
  response_batch: string | null;
  bot_run: string | null;
  notes: string;
  readiness_errors: string[];
  events: { action: string; created_at: string; note: string }[];
};
type SyntheticRow = {
  id: string;
  sequence: number;
  answers: Record<string, unknown>;
  data_label: string;
};
export default function OperatorOrder({
  order,
  onChange,
}: {
  order: Order;
  onChange: () => Promise<void>;
}) {
  const root = `/orders/${order.reference}/`;
  const [detail, setDetail] = useState<Detail | null>(null);
  const [schema, setSchema] = useState("");
  const [formId, setFormId] = useState(order.google_form_id);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [run, setRun] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [rows, setRows] = useState<Paginated<SyntheticRow> | null>(null);
  const [rowPage, setRowPage] = useState(1);
  const [rowRevision, setRowRevision] = useState(0);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const refresh = useCallback(async () => {
    const d = await api<Detail>(root + "operator_detail/");
    setDetail(d);
  }, [root]);
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    api<Version>(root + "schema/")
      .then((v) => {
        const questions = v.questions.map(
          ({
            key,
            position,
            text,
            type,
            required,
            template_page_number,
            validation_rules,
            options,
          }) => ({
            key,
            position,
            text,
            type,
            required,
            template_page_number,
            validation_rules,
            options: options.map(({ key, label, value, position }) => ({
              key,
              label,
              value,
              position,
            })),
          }),
        );
        setSchema(JSON.stringify(questions, null, 2));
        setMapping(Object.fromEntries(v.questions.map((q) => [q.key, q.text])));
      })
      .catch((e) => setError(e.message));
  }, [root, refresh]);
  useEffect(() => {
    if (!detail?.bot_run) return;
    api<Paginated<SyntheticRow>>(root + `synthetic-responses/?page=${rowPage}`)
      .then((data) => {
        setRows(data);
        setEdits(
          Object.fromEntries(
            data.results.map((row) => [
              row.id,
              JSON.stringify(row.answers, null, 2),
            ]),
          ),
        );
      })
      .catch((e) => setError(e.message));
  }, [root, rowPage, rowRevision, detail?.bot_run]);
  async function action(path: string, body: unknown = {}) {
    setBusy(true);
    setError("");
    try {
      await api(root + path + "/", {
        method: "POST",
        body: JSON.stringify(body),
      });
      await onChange();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Operator action failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mvp-panel operator-panel form-stack">
      <h2>Operator fulfillment</h2>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {order.status === "PAYMENT_SUBMITTED" && (
        <>
          <p>
            Claimed sender: {order.payment_sender_name || "Not supplied"} ·
            Transfer reference: {order.payment_reference || "Not supplied"} ·
            Claimed at: {order.payment_claimed_at || "Unknown"}
          </p>
          <p>
            Check the bank statement independently. A customer payment claim is
            not proof of transfer.
          </p>
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => void action("verify-payment")}
          >
            VERIFY PAYMENT
          </button>
          <label className="field">
            Payment rejection reason
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          <button
            className="btn btn-ghost"
            disabled={busy || !reason.trim()}
            onClick={() => void action("reject-payment", { reason })}
          >
            REJECT PAYMENT
          </button>
        </>
      )}
      {order.payment_status === "VERIFIED" && (
        <>
          <details>
            <summary>
              Prepare questionnaire schema ({order.question_count} questions)
            </summary>
            <p>
              Check types, required fields, options and template page numbers.
              Supported types: SHORT_TEXT, PARAGRAPH, SINGLE_CHOICE,
              MULTIPLE_CHOICE, DROPDOWN, LIKERT, LINEAR_SCALE, SINGLE_GRID,
              MULTIPLE_GRID, DATE, TIME, NUMBER. Use validation_rules for
              numeric bounds or grid rows/columns. Existing answer data cannot
              be overwritten here.
            </p>
            <label className="field">
              Question schema JSON
              <textarea
                aria-label="Question schema JSON"
                className="code-field"
                rows={16}
                value={schema}
                onChange={(e) => setSchema(e.target.value)}
              />
            </label>
            <button
              disabled={busy}
              onClick={() => {
                try {
                  void action("schema", { questions: JSON.parse(schema) });
                } catch {
                  setError("Schema must be valid JSON.");
                }
              }}
            >
              Save verified schema
            </button>
          </details>
          {["PAID", "NEEDS_REVIEW", "FAILED"].includes(order.status) && (
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void action("process")}
            >
              {order.processing_mode === "manual"
                ? "Start manual preparation"
                : "Queue processing / retry failed jobs"}
            </button>
          )}
          {order.service_type === "SYNTHETIC_DATA" && (
            <>
              <p>
                Internal generator only. Inspect every dataset. Complex grids
                and instructions may need manual correction. Google submission
                is blocked; labelled CSV is the supported delivery.
              </p>
              {order.status === "PROCESSING" && !detail?.bot_run && (
                <button
                  disabled={busy}
                  onClick={() => void action("generate-synthetic")}
                >
                  Generate synthetic TEST dataset
                </button>
              )}
              <label className="field">
                Attach an existing completed BotRun ID
                <input value={run} onChange={(e) => setRun(e.target.value)} />
              </label>
              <button
                disabled={busy || !run}
                onClick={() => void action("attach-bot-run", { bot_run: run })}
              >
                Attach completed BotRun
              </button>
              {rows && (
                <>
                  <h3>Inspect synthetic rows</h3>
                    <button onClick={() => setRowRevision(rowRevision + 1)}>Refresh generated rows</button>
                  {rows.results.map((row) => (
                    <div key={row.id}>
                      <strong>
                        #{row.sequence} · {row.data_label}
                      </strong>
                      <textarea
                        className="code-field"
                        rows={4}
                        value={edits[row.id] ?? ""}
                        onChange={(e) =>
                          setEdits({ ...edits, [row.id]: e.target.value })
                        }
                      />
                      <button
                        disabled={busy}
                        onClick={() => {
                          try {
                            void action("synthetic-responses", {
                              id: row.id,
                              answers: JSON.parse(edits[row.id]),
                            });
                          } catch {
                            setError("Answers must be valid JSON.");
                          }
                        }}
                      >
                        Save labelled row
                      </button>
                    </div>
                  ))}
                  <div className="pagination">
                    <button
                      disabled={!rows.previous}
                      onClick={() => setRowPage(rowPage - 1)}
                    >
                      Previous rows
                    </button>
                    <span>Page {rowPage}</span>
                    <button
                      disabled={!rows.next}
                      onClick={() => setRowPage(rowPage + 1)}
                    >
                      Next rows
                    </button>
                  </div>
                </>
              )}
            </>
          )}
          {order.service_type === "DIGITIZATION" && (
            <details>
              <summary>Prepare final Google Apps Script</summary>
              <label className="field">
                Google Form edit URL or ID
                <input
                  value={formId}
                  onChange={(e) => setFormId(e.target.value)}
                />
              </label>
              {Object.entries(mapping).map(([key, value]) => (
                <label className="field" key={key}>
                  {key}: exact Google Form item title
                  <input
                    value={value}
                    onChange={(e) =>
                      setMapping({ ...mapping, [key]: e.target.value })
                    }
                  />
                </label>
              ))}
              <button
                disabled={busy}
                onClick={() =>
                  void action("prepare-script", {
                    form_id: formId,
                    mappings: mapping,
                  })
                }
              >
                Prepare final script
              </button>
              <p>
                All respondents must be confirmed and valid. Mapping must be
                checked in Google before submission.
              </p>
            </details>
          )}
          {["PROCESSING", "NEEDS_REVIEW"].includes(order.status) && (
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={() => void action("ready")}
            >
              Mark order READY and notify customer
            </button>
          )}
        </>
      )}
      <label className="field">
        Internal note
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <button
        disabled={busy || !reason.trim()}
        onClick={() => void action("note", { reason })}
      >
        Record internal note
      </button>
      {detail && (
        <>
          <p>Saved note: {detail.notes || "None"}</p>
          <details>
            <summary>Readiness checks and audit trail</summary>
            <ul>
              {detail.readiness_errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
            {detail.events.map((e, i) => (
              <p key={i}>
                {new Date(e.created_at).toLocaleString()} · {e.action} {e.note}
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}
