"use client";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { Configuration, Order, money } from "@/lib/orders";
export default function OrderForm({
  synthetic = false,
}: {
  synthetic?: boolean;
}) {
  const router = useRouter();
  const [config, setConfig] = useState<Configuration | null>(null);
  const [count, setCount] = useState(1);
  const [pages, setPages] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Configuration>("/orders/configuration/", { auth: false })
      .then(setConfig)
      .catch((e) => setError(e.message));
  }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const data = new FormData(event.currentTarget);
    try {
      const order = await api<Order>("/orders/", {
        method: "POST",
        body: JSON.stringify({
          title: data.get("title"),
          service_type: synthetic ? "SYNTHETIC_DATA" : "DIGITIZATION",
          respondent_count: synthetic ? 0 : count,
          pages_per_respondent: synthetic ? 1 : pages,
          expected_page_count: pages,
          synthetic_response_count: synthetic ? count : 0,
          question_count: Number(data.get("question_count")),
          google_form_url: data.get("google_form_url"),
          instructions: data.get("instructions"),
          questions: String(data.get("questions") ?? "")
            .split("\n")
            .map((q) => q.trim())
            .filter(Boolean),
        }),
      });
      router.push(`/orders/${order.reference}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create order.");
      setBusy(false);
    }
  }
  const rate = Number(
    synthetic ? config?.synthetic_rate_ngn : config?.digitization_rate_ngn,
  );
  return (
    <>
      <header className="page-header">
        <div>
          <h1>
            {synthetic ? "Synthetic TEST data" : "Digitize your questionnaire"}
          </h1>
          <p>
            {synthetic
              ? "A human-assisted service for testing questionnaires, forms and data workflows."
              : "Turn completed paper questionnaires into an Apps Script for your existing Google Form."}
          </p>
        </div>
      </header>
      {synthetic && (
        <div className="notice">
          SYNTHETIC TEST DATA — not human research respondents. Upload one blank
          questionnaire; its pages are not respondents. We’ll notify you when
          your order is ready.
        </div>
      )}
      <form className="mvp-panel form-stack" onSubmit={submit}>
        <h2>1. Set up your order</h2>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <label className="field">
          Job title
          <input name="title" required maxLength={255} />
        </label>
        <div className="form-row">
          <label className="field">
            {synthetic
              ? "Synthetic responses requested"
              : "Number of respondents"}
            <input
              type="number"
              min={1}
              max={
                synthetic
                  ? config?.max_synthetic_responses
                  : config?.max_respondents
              }
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              required
            />
          </label>
          <label className="field">
            {synthetic
              ? "Pages in the one blank questionnaire"
              : "Pages per respondent"}
            <input
              type="number"
              min={1}
              max={100}
              value={pages}
              onChange={(e) => setPages(Number(e.target.value))}
              required
            />
          </label>
        </div>
        <label className="field">
          Number of questions
          <input
            name="question_count"
            type="number"
            min={1}
            max={500}
            required
            defaultValue={1}
          />
        </label>
        <label className="field">
          Google Form edit URL or ID (optional for now)
          <input
            name="google_form_url"
            maxLength={500}
            placeholder="https://docs.google.com/forms/d/FORM_ID/edit"
          />
          <small>
            Use the edit URL, not a forms.gle or published /d/e/ link. We do not
            verify Google ownership and never ask for your Google password.
          </small>
        </label>
        <label className="field">
          Questions, one per line (optional)
          <textarea
            name="questions"
            rows={6}
            placeholder="Enter every question, or leave this for the operator to prepare from your template."
          />
          <small>
            Quick setup creates draft text questions. An operator checks
            question types and options before processing.
          </small>
        </label>
        <label className="field">
          Instructions (optional)
          <textarea name="instructions" maxLength={10000} rows={3} />
        </label>
        <div className="notice">
          <strong>
            Expected upload: {synthetic ? pages : count * pages} physical pages
          </strong>
          <p>
            {synthetic
              ? `One blank questionnaire → ${count} synthetic TEST responses`
              : `${count} respondents × ${pages} pages → ${count} logical responses`}
          </p>
          <p>
            {Number.isFinite(rate) && rate > 0
              ? `Estimated total: ${money(count * rate)} (${money(rate)} per ${synthetic ? "synthetic response" : "respondent"})`
              : "Pricing is awaiting configuration."}
          </p>
        </div>
        <p>
          Next: upload and validate files, view bank instructions, submit
          payment for manual verification. Processing and results remain locked
          until verification.
        </p>
        <button
          className="btn btn-primary"
          disabled={busy || !config || !(rate > 0)}
        >
          {busy ? "Creating…" : "Create order and continue to upload"}
        </button>
      </form>
    </>
  );
}
