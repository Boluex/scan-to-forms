"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  FileText,
  Plus,
  ArrowRight,
  FlaskConical,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { Order, words, money } from "@/lib/orders";
import { Paginated } from "@/lib/types";
import { useUser } from "@/components/Workspace";
export default function OrdersPage() {
  const user = useUser();
  const [data, setData] = useState<Paginated<Order> | null>(null),
    [page, setPage] = useState(1),
    [filter, setFilter] = useState(""),
    [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError("");
    api<Paginated<Order>>(
      `/orders/?page=${page}${filter ? `&status=${filter}` : ""}`,
    )
      .then((value) => {
        if (!cancelled) setData(value);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [page, filter]);
  return (
    <>
      <header className="page-header">
        <div>
          <p className="section-kicker">Your workspace</p>
          <h1>
            {user?.is_staff
              ? "Customer orders"
              : `Hello, ${user?.name.split(" ")[0] || "researcher"}.`}
          </h1>
          <p>
            {user?.is_staff
              ? "Manage payments, review progress, and deliver results."
              : "A little less paperwork. A little more progress."}
          </p>
        </div>
        <Link className="btn btn-primary" href="/digitize">
          <Plus size={17} />
          New digitization
        </Link>
      </header>
      <section className="workspace-welcome">
        <div>
          <span className="section-kicker">From paper to possibility</span>
          <h2>Let’s move your research forward.</h2>
          <p>
            Upload your questionnaires. We’ll help turn the responses into data
            you can work with.
          </p>
          <Link href="/digitize">
            Start a questionnaire project <ArrowRight size={17} />
          </Link>
        </div>
        <div className="welcome-art" aria-hidden="true">
          <FileText size={66} strokeWidth={1} />
          <span>Upload → Review → Results</span>
        </div>
      </section>
      <div className="quick-links">
        <Link href="/digitize">
          <span className="section-icon">
            <FileText size={21} />
          </span>
          <div>
            <strong>Digitize questionnaires</strong>
            <small>Turn completed pages into reviewed responses</small>
          </div>
          <ArrowUpRight size={20} />
        </Link>
        <Link href="/synthetic">
          <span className="section-icon">
            <FlaskConical size={21} />
          </span>
          <div>
            <strong>Synthetic test data</strong>
            <small>Labelled sample data for testing workflows</small>
          </div>
          <ArrowUpRight size={20} />
        </Link>
      </div>
      <section className="orders-section">
        <div className="section-toolbar">
          <div>
            <h2>
              {user?.is_staff ? "All customer orders" : "My orders"}
              {data && <span className="count-chip">{data.count}</span>}
            </h2>
            <p>Keep track of every step, from upload to delivery.</p>
          </div>
          <label className="filter-label">
            <span className="sr-only">Filter status</span>
            <select
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              {[
                "UPLOADING",
                "AWAITING_PAYMENT",
                "PAYMENT_SUBMITTED",
                "PAID",
                "QUEUED",
                "PROCESSING",
                "NEEDS_REVIEW",
                "READY",
                "COMPLETED",
                "FAILED",
              ].map((s) => (
                <option key={s} value={s}>
                  {words(s).toLowerCase()}
                </option>
              ))}
            </select>
          </label>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!data && !error && (
          <p role="status" className="list-loading">
            Loading orders…
          </p>
        )}
        <div className="order-list">
          {data?.results.map((order) => (
            <Link
              className="project-row"
              key={order.reference}
              href={`/orders/${order.reference}`}
            >
              <span className="project-icon">
                {order.service_type === "DIGITIZATION" ? (
                  <FileText size={21} />
                ) : (
                  <FlaskConical size={21} />
                )}
              </span>
              <div className="project-copy">
                <strong>{order.title}</strong>
                <small>
                  {order.reference} ·{" "}
                  {order.service_type === "DIGITIZATION"
                    ? `${order.respondent_count} respondents · ${order.expected_page_count} pages`
                    : `${order.synthetic_response_count} synthetic TEST responses`}
                </small>
                <small>
                  Payment: {words(order.payment_status).toLowerCase()}
                </small>
              </div>
              <span
                className={`order-status status-${order.status.toLowerCase()}`}
              >
                {words(order.status).toLowerCase()}
              </span>
              <span className="project-price">{money(order.amount_ngn)}</span>
              <ArrowUpRight size={17} />
            </Link>
          ))}
        </div>
        {data?.count === 0 && (
          <div className="orders-empty">
            <span className="empty-icon">
              <Search size={25} />
            </span>
            <h3>
              {filter
                ? "No orders with this status"
                : "Your next project starts here"}
            </h3>
            <p>
              {filter
                ? "Choose another status to find your orders."
                : "Create your first order and keep all your questionnaire work in one place."}
            </p>
            {!filter && (
              <Link className="btn btn-secondary" href="/digitize">
                Create an order <ArrowRight size={16} />
              </Link>
            )}
          </div>
        )}
        {!!data?.count && (
          <div className="pagination">
            <span>
              Page {page} · {data.count} orders
            </span>
            <button disabled={!data.previous} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <button disabled={!data.next} onClick={() => setPage(page + 1)}>
              Next
            </button>
          </div>
        )}
      </section>
    </>
  );
}
