"use client";

import { AlertTriangle, CheckCircle2, FileWarning, Save } from "lucide-react";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { authorizedFetch, api } from "@/lib/api";
import type {
  Answer,
  Paginated,
  QuestionnaireResponse,
  ResponsePage,
} from "@/lib/types";

function confidenceInfo(answer: Answer) {
  const value = Number(answer.confidence ?? 0);
  if (value >= 0.85)
    return { label: `${Math.round(value * 100)}%`, level: "high" };
  if (value >= 0.65)
    return { label: `${Math.round(value * 100)}%`, level: "medium" };
  return {
    label: value ? `${Math.round(value * 100)}%` : "Review",
    level: "low",
  };
}

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>();
  const orderReference = useSearchParams().get("order");
  const [targetSequence, setTargetSequence] = useState(1);
  const [response, setResponse] = useState<QuestionnaireResponse | null>(null);
  const [batchResponses, setBatchResponses] = useState<QuestionnaireResponse[]>(
    [],
  );
  const [values, setValues] = useState<Record<string, string>>({});
  const [selectedPageId, setSelectedPageId] = useState<string | null>(null);
  const [documentUrl, setDocumentUrl] = useState<string | null>(null);
  const [assignedPage, setAssignedPage] = useState(1);
  const [targetResponse, setTargetResponse] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadResponse = useCallback(async () => {
    const data = await api<QuestionnaireResponse>(`/responses/${id}/`);
    setResponse(data);
    setValues(
      Object.fromEntries(
        data.answers.map((answer) => [
          answer.id,
          ["MULTIPLE_CHOICE", "SINGLE_GRID", "MULTIPLE_GRID"].includes(
            answer.question_type,
          )
            ? JSON.stringify(answer.value_json)
            : answer.value_text,
        ]),
      ),
    );
    setSelectedPageId((current) =>
      data.pages.some((page) => page.id === current)
        ? current
        : (data.pages[0]?.id ?? null),
    );
    setTargetResponse(data.id);
    const related = await api<Paginated<QuestionnaireResponse>>(
      `/responses/?batch=${data.batch}`,
    );
    setBatchResponses(related.results);
  }, [id]);

  useEffect(() => {
    loadResponse().catch((caught) =>
      setError(
        caught instanceof Error ? caught.message : "Unable to load response.",
      ),
    );
  }, [loadResponse]);

  const selectedPage = useMemo(
    () => response?.pages.find((page) => page.id === selectedPageId) ?? null,
    [response, selectedPageId],
  );
  useEffect(() => {
    if (!selectedPage) {
      setDocumentUrl(null);
      return;
    }
    setAssignedPage(selectedPage.assigned_template_page_number ?? 1);
    setTargetResponse(selectedPage.response);
    let objectUrl: string | null = null;
    const controller = new AbortController();
    let active = true;
    setDocumentUrl(null);
    authorizedFetch(`/documents/${selectedPage.document_id}/file/`, {signal: controller.signal})
      .then(async (file) => {
        if (!file.ok) throw new Error("Unable to open this response page.");
        const blob = await file.blob();
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setDocumentUrl(
          `${objectUrl}${selectedPage.content_type === "application/pdf" ? `#page=${selectedPage.source_page_number}` : ""}`,
        );
      })
      .catch((caught) =>
        active && setError(
          caught instanceof Error
            ? caught.message
            : "Unable to open this response page.",
        ),
      );
    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [selectedPage]);

  const changed = useMemo(
    () =>
      response?.answers.filter(
        (answer) => values[answer.id] !== answer.value_text,
      ) ?? [],
    [response, values],
  );
  const groupingIssueCount =
    (response?.validation_issues.length ?? 0) +
    (response?.pages.reduce(
      (total, page) => total + page.validation_issues.length,
      0,
    ) ?? 0);
  const blockingGroupingIssueCount =
    (response?.validation_issues.filter((issue) => issue.severity === "ERROR")
      .length ?? 0) +
    (response?.pages.reduce(
      (total, page) => total + page.validation_issues.length,
      0,
    ) ?? 0);

  async function saveAnswers(confirm: boolean) {
    if (!response) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      for (const answer of response.answers) {
        const structured = [
          "MULTIPLE_CHOICE",
          "SINGLE_GRID",
          "MULTIPLE_GRID",
        ].includes(answer.question_type);
        const payload = structured
          ? { value_json: JSON.parse(values[answer.id]), value_text: "" }
          : { value_text: values[answer.id], value_json: {} };
        await api(`/answers/${answer.id}/`, {
          method: "PATCH",
          body: JSON.stringify({
            ...payload,
            review_status: "APPROVED",
          }),
        });
      }
      if (confirm) {
        await api<QuestionnaireResponse>(`/responses/${response.id}/confirm/`, {
          method: "POST",
          body: JSON.stringify({}),
        });
        await loadResponse();
        setMessage(
          "Respondent confirmed. Return to the order to review the next respondent.",
        );
      } else {
        await loadResponse();
        setMessage("Answer corrections saved.");
      }
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Review could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function inspectPage() {
    if (!selectedPage || !orderReference) return;
    setSaving(true);
    setError("");
    try {
      await api(`/orders/${orderReference}/manual-page-reviewed/`, {
        method: "POST",
        body: JSON.stringify({ page_id: selectedPage.id }),
      });
      await loadResponse();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Inspection failed.");
    } finally {
      setSaving(false);
    }
  }

  async function correctPage() {
    if (!selectedPage) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await api<ResponsePage>(`/response-pages/${selectedPage.id}/`, {
        method: "PATCH",
        body: JSON.stringify({
          response: targetResponse,
          assigned_template_page_number: assignedPage,
        }),
      });
      await loadResponse();
      setMessage(
        "Page assignment corrected and respondent answers re-aggregated.",
      );
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Page assignment could not be corrected.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (error && !response)
    return (
      <div className="page-content">
        <div className="form-error">{error}</div>
      </div>
    );
  if (!response)
    return (
      <div className="loading-screen">
        <div className="spinner" />
      </div>
    );
  const unresolved = response.answers.filter(
    (answer) => answer.review_status === "NEEDS_REVIEW",
  ).length;
  const slots = Array.from(
    { length: response.expected_page_count },
    (_, index) => index + 1,
  );
  return (
    <div className="review-page">
      <section className="document-pane">
        <header className="pane-head">
          <div>
            <h2>
              {response.respondent_reference ||
                `Respondent #${response.sequence ?? "—"}`}
            </h2>
            <span>
              {response.uploaded_page_count}/{response.expected_page_count}{" "}
              physical pages
            </span>
          </div>
          <span className={`status status-${response.status.toLowerCase()}`}>
            {response.status.replaceAll("_", " ")}
          </span>
        </header>
        <div className="page-completeness">
          {slots.map((slot) => {
            const present = response.pages.some(
              (page) => page.assigned_template_page_number === slot,
            );
            return (
              <span className={present ? "present" : "missing"} key={slot}>
                {present ? "✓" : "✕"} Page {slot}
              </span>
            );
          })}
        </div>
        <div className="page-tabs">
          {response.pages.map((page) => (
            <button
              key={page.id}
              className={selectedPageId === page.id ? "active" : ""}
              onClick={() => setSelectedPageId(page.id)}
            >
              <strong>Page {page.assigned_template_page_number ?? "?"}</strong>
              <span>upload #{page.original_upload_order}</span>
              {page.validation_issues.length > 0 && <AlertTriangle size={12} />}
            </button>
          ))}
        </div>
        {documentUrl ? (
          <iframe
            className="document-frame"
            src={documentUrl}
            title="Original questionnaire page"
          />
        ) : (
          <div className="document-loading">Preparing secure page preview…</div>
        )}
        {selectedPage && (
          <div className="page-correction">
            <h3>Correct this page</h3>
            {orderReference && (
              <p>
                <a href={`/orders/${orderReference}`}>
                  Return to order / append missing pages
                </a>
              </p>
            )}
            <p>Processing: {selectedPage.processing_status}</p>
            {orderReference &&
              selectedPage.processing_status !== "COMPLETED" && (
                <button disabled={saving} onClick={inspectPage}>
                  Record manual page inspection (manual mode only)
                </button>
              )}
            {selectedPage.processing_status === "FAILED" && (
              <button
                onClick={async () => {
                  try {
                    await api(`/documents/${selectedPage.document_id}/retry/`, {
                      method: "POST",
                    });
                    await loadResponse();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Retry failed.");
                  }
                }}
              >
                Retry failed OCR
              </button>
            )}
            <div className="form-row">
              <div className="field">
                <label htmlFor="assigned-page">Questionnaire page</label>
                <select
                  id="assigned-page"
                  value={assignedPage}
                  onChange={(event) =>
                    setAssignedPage(Number(event.target.value))
                  }
                >
                  {slots.map((slot) => (
                    <option key={slot} value={slot}>
                      Page {slot}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="target-response">Move to respondent</label>
                <label>
                  Find respondent by sequence
                  <input
                    type="number"
                    min={1}
                    value={targetSequence}
                    onChange={(e) => setTargetSequence(Number(e.target.value))}
                  />
                </label>
                <button
                  onClick={async () => {
                    try {
                      const result = await api<
                        Paginated<QuestionnaireResponse>
                      >(
                        `/responses/?batch=${response.batch}&sequence=${targetSequence}`,
                      );
                      setBatchResponses(result.results);
                      if (result.results[0])
                        setTargetResponse(result.results[0].id);
                    } catch (e) {
                      setError(
                        e instanceof Error ? e.message : "Lookup failed.",
                      );
                    }
                  }}
                >
                  Find respondent
                </button>
                <select
                  id="target-response"
                  value={targetResponse}
                  onChange={(event) => setTargetResponse(event.target.value)}
                >
                  {batchResponses.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.respondent_reference ||
                        `Respondent #${item.sequence}`}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <button
              className="btn btn-ghost"
              disabled={saving}
              onClick={correctPage}
            >
              Apply page correction
            </button>
            <p className="form-note">
              Individual images can move between respondents. Pages inside one
              PDF stay together, but their questionnaire page numbers can be
              corrected.
            </p>
            {selectedPage.validation_issues.map((issue) => (
              <div
                className="inline-warning"
                key={`${selectedPage.id}-${issue.code}`}
              >
                <FileWarning size={13} /> {issue.message}
              </div>
            ))}
          </div>
        )}
      </section>
      <section className="answers-pane">
        <header className="pane-head">
          <div>
            <h2>{response.questionnaire_title}</h2>
            <span>{response.respondent_reference}</span>
          </div>
          <span className={`status status-${response.status.toLowerCase()}`}>
            {response.status.replaceAll("_", " ")}
          </span>
        </header>
        <div className="answers-scroll">
          {error && <div className="form-error">{error}</div>}
          {message && <div className="form-success">{message}</div>}
          {response.validation_issues.length > 0 && (
            <div className="response-warning-list">
              <strong>
                <AlertTriangle size={15} /> Response-page warnings
              </strong>
              {response.validation_issues.map((issue) => (
                <p key={issue.code}>{issue.message}</p>
              ))}
            </div>
          )}
          {response.answers.map((answer, index) => {
            const confidence = confidenceInfo(answer);
            return (
              <article
                className={`answer-card ${confidence.level === "low" ? "low" : ""}`}
                key={answer.id}
              >
                <div className="answer-top">
                  <span className="answer-number">{index + 1}</span>
                  <span className="answer-question">
                    {answer.question_text}
                  </span>
                  <span className={`confidence ${confidence.level}`}>
                    {confidence.label}
                  </span>
                </div>
                <input
                  className="answer-input"
                    disabled={saving}
                  value={values[answer.id] ?? ""}
                  onChange={(event) =>
                    setValues({ ...values, [answer.id]: event.target.value })
                  }
                  placeholder={
                    [
                      "MULTIPLE_CHOICE",
                      "SINGLE_GRID",
                      "MULTIPLE_GRID",
                    ].includes(answer.question_type)
                      ? "JSON array or grid object"
                      : "Enter or correct the answer"
                  }
                />
                <div className="answer-meta">
                  <span>
                    {answer.options
                      .map((o) => `${o.key}: ${o.label}`)
                      .join(" · ")}{" "}
                  </span>
                  <span>
                    {answer.question_type.replaceAll("_", " ").toLowerCase()}
                  </span>
                  <span>
                    {answer.review_status.replaceAll("_", " ").toLowerCase()}
                  </span>
                </div>
              </article>
            );
          })}
          {response.answers.length === 0 && (
            <div className="empty-state">
              <h3>Answers are not ready yet.</h3>
              <p>
                Resolve missing/failed pages or wait for all page OCR jobs to
                finish.
              </p>
            </div>
          )}
        </div>
        <footer className="review-footer">
          <span>
            {groupingIssueCount} page issue(s) · {unresolved} low-confidence
            answer(s) · {changed.length} edited
          </span>
          <div className="review-actions">
            <button
              className="btn btn-ghost"
              onClick={() => saveAnswers(false)}
              disabled={saving || response.answers.length === 0}
            >
              <Save size={15} /> Save corrections
            </button>
            <button
              className="btn btn-primary"
              onClick={() => saveAnswers(true)}
              disabled={
                saving ||
                response.answers.length === 0 ||
                blockingGroupingIssueCount > 0
              }
            >
              {saving ? (
                <>
                  <Save size={15} /> Saving…
                </>
              ) : (
                <>
                  <CheckCircle2 size={15} /> Approve all answers and confirm
                </>
              )}
            </button>
          </div>
        </footer>
      </section>
    </div>
  );
}
