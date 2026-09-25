"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, download } from "@/lib/api";
import { Order, Upload, Respondent, money, words } from "@/lib/orders";
import { Paginated } from "@/lib/types";
import { useUser } from "@/components/Workspace";
import OrderUploads from "@/components/OrderUploads";
import OperatorOrder from "@/components/OperatorOrder";
import ScriptInstructions from "@/components/ScriptInstructions";
export default function OrderPage() {
  const { reference } = useParams<{ reference: string }>();
  const root = `/orders/${reference}/`;
  const user = useUser();
  const [order, setOrder] = useState<Order | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [sender, setSender] = useState(""),
    [paymentRef, setPaymentRef] = useState(""),
    [script, setScript] = useState(""),
    [copied, setCopied] = useState(false);
  const [uploads, setUploads] = useState<Paginated<Upload> | null>(null),
    [respondents, setRespondents] = useState<Paginated<Respondent> | null>(
      null,
    ),
    [page, setPage] = useState(1),
    [uploadPage, setUploadPage] = useState(1);
  const refresh = useCallback(async () => {
    const [o, u, r] = await Promise.all([
      api<Order>(root),
      api<Paginated<Upload>>(root + `uploads/?page=${uploadPage}`),
      api<Paginated<Respondent>>(root + `respondents/?page=${page}`),
    ]);
    setOrder(o);
    setUploads(u);
    setRespondents(r);
    if (!o.result_available) setScript("");
  }, [root, page, uploadPage]);
  useEffect(() => {
    refresh().catch((e) => setError(e.message));
    const timer = setInterval(
      () => refresh().catch((e) => setError(e.message)),
      30000,
    );
    return () => clearInterval(timer);
  }, [refresh]);
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  if (!order)
    return (
      <p role={error ? "alert" : undefined}>{error || "Loading order…"}</p>
    );
  return (
    <div className="form-stack">
      <Link href="/orders">← My Orders</Link>
      <h1>
        {order.reference} · {order.title}
      </h1>
      <p>
        {words(order.service_type)} · Created{" "}
        {new Date(order.created_at).toLocaleDateString()}
      </p>
      <div className="mvp-panel">
        <strong>Payment: {words(order.payment_status)}</strong>
        <p>Order: {words(order.status)}</p>
        <p>Total: {money(order.amount_ngn)}</p>
        {order.service_type === "SYNTHETIC_DATA" ? (
          <p>
            <strong>SYNTHETIC TEST DATA</strong> ·{" "}
            {order.synthetic_response_count} requested responses. These are not
            human research participants.
          </p>
        ) : (
          <p>
            {order.respondent_count} respondents × {order.pages_per_respondent}{" "}
            pages = {order.expected_page_count} expected physical pages.
          </p>
        )}
        <p>
          Uploaded: {order.uploads_summary.uploaded_pages} /{" "}
          {order.expected_page_count} pages ·{" "}
          {order.uploads_summary.complete
            ? "Upload complete"
            : "Upload incomplete"}
        </p>
        {order.processing_mode === "manual" && (
          <p>
            Operator-assisted preparation. Automatic OCR is not running in this
            environment.
          </p>
        )}
      </div>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {(order.status === "UPLOADING" ||
        (user?.is_staff &&
          ["PAID", "NEEDS_REVIEW", "FAILED"].includes(order.status))) && (
        <OrderUploads order={order} onChange={refresh} />
      )}
      {order.status === "UPLOADING" && (
        <button
          className="btn btn-primary"
          disabled={busy || !order.uploads_summary.complete}
          onClick={() =>
            void act(() => api(root + "submit/", { method: "POST" }))
          }
        >
          Validate uploads and continue to payment
        </button>
      )}
      {order.status === "AWAITING_PAYMENT" && (
        <section className="mvp-panel form-stack">
          <h2>Bank transfer</h2>
          {order.payment_rejection_reason && (
            <p role="alert">
              Payment rejected: {order.payment_rejection_reason}
            </p>
          )}
          {order.bank ? (
            <>
              <p>
                Transfer exactly <strong>{money(order.amount_ngn)}</strong>. Use{" "}
                {order.reference} as the payment reference.
              </p>
              <dl>
                <dt>Bank</dt>
                <dd>{order.bank.bank_name}</dd>
                <dt>Account name</dt>
                <dd>{order.bank.account_name}</dd>
                <dt>Account number</dt>
                <dd>{order.bank.account_number}</dd>
              </dl>
              <label className="field">
                Sender name (optional)
                <input
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                />
              </label>
              <label className="field">
                Transfer reference (optional)
                <input
                  value={paymentRef}
                  onChange={(e) => setPaymentRef(e.target.value)}
                />
              </label>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() =>
                  void act(() =>
                    api(root + "payment-claim/", {
                      method: "POST",
                      body: JSON.stringify({
                        sender_name: sender,
                        reference: paymentRef,
                      }),
                    }),
                  )
                }
              >
                I HAVE PAID
              </button>
              <p>
                We will check the bank transfer manually. This button does not
                verify payment or unlock processing.
              </p>
            </>
          ) : (
            <p>
              Bank transfer is currently unavailable. Contact the operator
              before transferring.
            </p>
          )}
        </section>
      )}
      {order.status === "PAYMENT_SUBMITTED" && (
        <p className="mvp-panel">
          Your payment claim is awaiting manual verification. Processing and
          results remain locked.
        </p>
      )}
      {["PAID", "QUEUED", "PROCESSING", "NEEDS_REVIEW"].includes(
        order.status,
      ) && (
        <p>
          We’re preparing your order. We’ll notify you when your order is ready.
        </p>
      )}
      {order.result_available && (
        <section className="mvp-panel form-stack">
          <h2>Your result is ready</h2>
          {order.service_type === "SYNTHETIC_DATA" && (
            <p>
              <strong>SYNTHETIC TEST DATA</strong> — for testing only. Google
              submission is not enabled for this service.
            </p>
          )}
          <div className="button-row">
            <button
              disabled={busy}
              onClick={() =>
                void act(() =>
                  download(
                    root + "export/?file_format=csv",
                    `${reference}.csv`,
                  ),
                )
              }
            >
              Download{" "}
              {order.service_type === "SYNTHETIC_DATA"
                ? "labelled synthetic "
                : ""}
              CSV
            </button>
            {order.service_type === "DIGITIZATION" && (
              <>
                <button
                  disabled={busy}
                  onClick={() =>
                    void act(() =>
                      download(
                        root + "export/?file_format=xlsx",
                        `${reference}.xlsx`,
                      ),
                    )
                  }
                >
                  Download XLSX
                </button>
                <button
                  onClick={() =>
                    void act(async () => {
                      const data = await api<{ script: string }>(
                        root + "script/",
                      );
                      setScript(data.script);
                    })
                  }
                >
                  Open Apps Script
                </button>
                <button
                  onClick={() =>
                    void act(() =>
                      download(root + "script/?download=1", `${reference}.gs`),
                    )
                  }
                >
                  Download .GS
                </button>
              </>
            )}
          </div>
          {script && (
            <>
              <button
                onClick={() =>
                  void act(async () => {
                    await navigator.clipboard.writeText(script);
                    setCopied(true);
                  })
                }
              >
                {copied ? "Copied" : "COPY CODE"}
              </button>
              <textarea
                aria-label="Generated Apps Script"
                className="code-field"
                readOnly
                rows={12}
                value={script}
              />
              <ScriptInstructions />
            </>
          )}
          {order.status === "READY" && (
            <button
              onClick={() =>
                void act(() => api(root + "complete/", { method: "POST" }))
              }
            >
              Acknowledge result received
            </button>
          )}
        </section>
      )}
      <section className="mvp-panel">
        <h2>Uploaded files</h2>
        {uploads?.results.map((u) => (
          <div className="order-row" key={u.id}>
            <span>
              {u.filename} · {u.page_count} page(s) ·{" "}
              {u.respondent_sequence
                ? `Respondent ${u.respondent_sequence}`
                : "Questionnaire template"}{" "}
              · {u.status}
            </span>
            <button
              onClick={() =>
                void act(() =>
                  download(root + `uploads/${u.id}/file/`, u.filename),
                )
              }
            >
              Original file
            </button>
            {["UPLOADING", "AWAITING_PAYMENT"].includes(order.status) && (
              <button
                disabled={busy}
                onClick={() =>
                  void act(() =>
                    api(root + `uploads/${u.id}/`, { method: "DELETE" }),
                  )
                }
              >
                Remove
              </button>
            )}
          </div>
        ))}
        <div className="pagination">
          <button
            disabled={!uploads?.previous}
            onClick={() => setUploadPage(uploadPage - 1)}
          >
            Previous files
          </button>
          <span>Page {uploadPage}</span>
          <button
            disabled={!uploads?.next}
            onClick={() => setUploadPage(uploadPage + 1)}
          >
            Next files
          </button>
        </div>
      </section>
      {order.service_type === "DIGITIZATION" && (
        <section className="mvp-panel">
          <h2>Respondents ({respondents?.count ?? 0})</h2>
          {respondents?.results.map((r) => (
            <div className="order-row" key={r.id}>
              <span>
                #{r.sequence} · {words(r.status)} · {r.uploaded_pages}/
                {r.expected_pages} pages
                {r.missing_pages.length > 0 &&
                  ` · Missing: ${r.missing_pages.join(", ")}`}
                {r.failed_pages > 0 && ` · ${r.failed_pages} failed pages`}
                {r.issues.map((i) => ` · ${i.message}`).join("")}
              </span>
              {user?.is_staff && order.payment_status === "VERIFIED" && (
                <Link href={`/dashboard/review/${r.id}?order=${reference}`}>
                  Review respondent
                </Link>
              )}
            </div>
          ))}
          <div className="pagination">
            <button
              disabled={!respondents?.previous}
              onClick={() => setPage(page - 1)}
            >
              Previous respondents
            </button>
            <span>Page {page}</span>
            <button
              disabled={!respondents?.next}
              onClick={() => setPage(page + 1)}
            >
              Next respondents
            </button>
          </div>
        </section>
      )}
      {user?.is_staff && <OperatorOrder order={order} onChange={refresh} />}
    </div>
  );
}
