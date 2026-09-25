"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Paginated } from "@/lib/types";
type Notice = {
  id: string;
  title: string;
  message: string;
  read_at: string | null;
  created_at: string;
  data: { order_reference?: string };
};
export default function Notifications() {
  const [data, setData] = useState<Paginated<Notice> | null>(null),
    [page, setPage] = useState(1),
    [error, setError] = useState("");
  const load = useCallback(
    async () =>
      setData(await api<Paginated<Notice>>(`/notifications/?page=${page}`)),
    [page],
  );
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [load]);
  async function read(id?: string) {
    try {
      await api(`/notifications/${id ? id + "/mark-read" : "mark-all-read"}/`, {
        method: "POST",
      });
      await load();
      window.dispatchEvent(new Event("notifications-updated"));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to update notification.",
      );
    }
  }
  return (
    <div className="form-stack">
      <h1>Notifications</h1>
      {error && <p role="alert">{error}</p>}
      <button onClick={() => void read()}>Mark all read</button>
      {data?.results.map((n) => (
        <article className="mvp-panel" key={n.id}>
          <h2>
            {!n.read_at && "● "}
            {n.title}
          </h2>
          <p>{n.message}</p>
          <small>{new Date(n.created_at).toLocaleString()}</small>
          {n.data.order_reference && (
            <p>
              <Link href={`/orders/${n.data.order_reference}`}>
                Open {n.data.order_reference}
              </Link>
            </p>
          )}
          {!n.read_at && (
            <button onClick={() => void read(n.id)}>Mark read</button>
          )}
        </article>
      ))}
      {data?.count === 0 && <p>No notifications yet.</p>}
      <div className="pagination">
        <button disabled={!data?.previous} onClick={() => setPage(page - 1)}>
          Previous
        </button>
        <span>Page {page}</span>
        <button disabled={!data?.next} onClick={() => setPage(page + 1)}>
          Next
        </button>
      </div>
    </div>
  );
}
