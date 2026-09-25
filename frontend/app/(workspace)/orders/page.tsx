"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Order, words, money } from "@/lib/orders";
import { Paginated } from "@/lib/types";
import { useUser } from "@/components/Workspace";
export default function OrdersPage() {
  const user = useUser();
  const [data, setData] = useState<Paginated<Order> | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api<Paginated<Order>>(
      `/orders/?page=${page}${filter ? `&status=${filter}` : ""}`,
    )
      .then(setData)
      .catch((e) => setError(e.message));
  }, [page, filter]);
  return (
    <>
      <header className="page-header">
        <div>
          <h1>{user?.is_staff ? "Customer orders" : "My orders"}</h1>
          <p>Track uploads, payment verification and reviewed results.</p>
        </div>
        <Link className="btn btn-primary" href="/digitize">
          New digitization
        </Link>
      </header>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <label className="field">
        Filter status
        <select
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All orders</option>
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
            <option key={s}>{s}</option>
          ))}
        </select>
      </label>
      <div className="order-list">
        {data?.results.map((order) => (
          <Link
            className="mvp-panel order-card"
            key={order.reference}
            href={`/orders/${order.reference}`}
          >
            <strong>
              {order.reference} · {order.title}
            </strong>
            <p>
              {order.service_type === "DIGITIZATION"
                ? `${order.respondent_count} respondents · ${order.expected_page_count} pages`
                : `${order.synthetic_response_count} SYNTHETIC TEST responses`}
            </p>
            <p>
              Payment: {words(order.payment_status)} · Processing:{" "}
              {words(order.status)}
            </p>
            <span>{money(order.amount_ngn)}</span>
          </Link>
        ))}
      </div>
      {data?.count === 0 && (
        <p>
          No orders yet. Choose Digitize Questionnaire or Synthetic Test Data to
          begin.
        </p>
      )}
      <div className="pagination">
        <button disabled={!data?.previous} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span>
          Page {page} · {data?.count ?? 0} orders
        </span>
        <button disabled={!data?.next} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
    </>
  );
}
