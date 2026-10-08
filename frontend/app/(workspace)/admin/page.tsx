"use client";
import Link from "next/link";
import ConfirmationDialog from "@/components/ConfirmationDialog";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Users, Files, CreditCard, Bell, ArrowRight } from "lucide-react";
import { useUser } from "@/components/Workspace";
import { api } from "@/lib/api";
import type { Paginated, User } from "@/lib/types";
type ManagedUser = User & { is_active: boolean; date_joined: string };
type Overview = {
  users: number;
  active_users: number;
  orders: number;
  payment_pending: number;
  push_pending: number;
  push_failed: number;
  orders_by_status: Record<string, number>;
  recent_activity: {
    id: number;
    action: string;
    actor__email: string;
    created_at: string;
  }[];
};
export default function AdminPage() {
  const me = useUser(),
    allowed = !!me?.is_staff && (me.is_superuser || me.role === "ADMIN");
  const [overview, setOverview] = useState<Overview | null>(null),
    [users, setUsers] = useState<Paginated<ManagedUser> | null>(null),
    [search, setSearch] = useState(""),
    [query, setQuery] = useState(""),
    [page, setPage] = useState(1),
    [error, setError] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [confirm, setConfirm] = useState<{
      user: ManagedUser;
      action: string;
    } | null>(null),
    [announcement, setAnnouncement] = useState<{
      title: string;
      message: string;
    } | null>(null);
  const load = useCallback(async () => {
    const [stats, people] = await Promise.all([
      api<Overview>("/operations/overview/"),
      api<Paginated<ManagedUser>>(
        `/operations/users/?page=${page}&search=${encodeURIComponent(query)}`,
      ),
    ]);
    setOverview(stats);
    setUsers(people);
  }, [page, query]);
  useEffect(() => {
    if (allowed) load().catch((e) => setError(e.message));
  }, [allowed, load]);
  async function control() {
    if (!confirm) return;
    setBusy(true);
    setError("");
    try {
      await api(`/operations/users/${confirm.user.id}/control/`, {
        method: "POST",
        body: JSON.stringify({ action: confirm.action }),
      });
      setMessage("User updated.");
      setConfirm(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to update user.");
    } finally {
      setBusy(false);
    }
  }
  function preview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setAnnouncement({
      title: String(form.get("title")),
      message: String(form.get("message")),
    });
  }
  async function broadcast() {
    if (!announcement) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ recipients: number }>(
        "/operations/announcements/",
        { method: "POST", body: JSON.stringify(announcement) },
      );
      setMessage(
        `Announcement saved for ${result.recipients} users. Push delivery is queued for enabled devices.`,
      );
      setAnnouncement(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to send announcement.");
    } finally {
      setBusy(false);
    }
  }
  if (!allowed)
    return (
      <section className="mvp-panel">
        <h1>Administrator access required</h1>
        <p>This area is available to account administrators.</p>
        <Link href="/orders">Return to orders</Link>
      </section>
    );
  return (
    <>
      <header className="page-header">
        <div>
          <p className="section-kicker">Administration</p>
          <h1>A clear view of your operations.</h1>
          <p>Manage people, keep orders moving, and share important updates.</p>
        </div>
        <Link href="/orders" className="btn btn-primary">
          Manage orders <ArrowRight size={16} />
        </Link>
      </header>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="form-success" role="status">
          {message}
        </p>
      )}
      <div className="admin-metrics">
        {[
          { title: "Registered users", value: overview?.users, icon: Users },
          { title: "Total orders", value: overview?.orders, icon: Files },
          {
            title: "Payments to verify",
            value: overview?.payment_pending,
            icon: CreditCard,
          },
          {
            title: "Push updates queued",
            value: overview?.push_pending,
            icon: Bell,
          },
        ].map(({ title, value, icon: Icon }) => (
          <article key={title}>
            <div>
              <span>{title}</span>
              <Icon size={18} />
            </div>
            <strong>{value ?? "—"}</strong>
          </article>
        ))}
      </div>
      <div className="admin-grid">
        <section className="mvp-panel">
          <div className="section-toolbar">
            <div>
              <h2>Users</h2>
              <p>Search accounts and manage access.</p>
            </div>
          </div>
          <form
            className="admin-search"
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(search);
              setPage(1);
            }}
          >
            <label className="sr-only" htmlFor="user-search">
              Search users
            </label>
            <input
              id="user-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, email or institution"
            />
            <button className="btn btn-secondary">Search</button>
          </form>
          <div className="user-list">
            {users?.results.map((user) => (
              <article key={user.id}>
                <div>
                  <strong>{user.name}</strong>
                  <small>{user.email}</small>
                  <span className="account-state">
                    {user.account_status.toLowerCase()} ·{" "}
                    {user.is_staff ? "operator" : "user"}
                  </span>
                </div>
                {String(user.id) !== String(me?.id) &&
                  !user.is_superuser &&
                  (!user.is_staff || me?.is_superuser) && (
                    <div className="user-controls">
                      <button
                        disabled={busy}
                        onClick={() =>
                          setConfirm({
                            user,
                            action: user.is_active ? "suspend" : "reactivate",
                          })
                        }
                      >
                        {user.is_active ? "Suspend" : "Reactivate"}
                      </button>
                      {me?.is_superuser && (
                        <button
                          disabled={busy}
                          onClick={() =>
                            setConfirm({
                              user,
                              action: user.is_staff
                                ? "revoke_operator"
                                : "grant_operator",
                            })
                          }
                        >
                          {user.is_staff ? "Remove operator" : "Make operator"}
                        </button>
                      )}
                    </div>
                  )}
              </article>
            ))}
          </div>
          {users?.count === 0 && <p>No matching users.</p>}
          <div className="pagination">
            <span>Page {page}</span>
            <button
              disabled={!users?.previous}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <button disabled={!users?.next} onClick={() => setPage(page + 1)}>
              Next
            </button>
          </div>
        </section>
        <section className="mvp-panel">
          <div className="section-icon">
            <Bell size={22} />
          </div>
          <h2>Share an announcement</h2>
          <p>
            Send an update to every active user’s inbox and enabled devices.
          </p>
          <form className="form-stack" onSubmit={preview}>
            <label className="field">
              Title
              <input
                name="title"
                required
                maxLength={180}
                placeholder="A short, clear headline"
              />
            </label>
            <label className="field">
              Message
              <textarea
                name="message"
                required
                maxLength={2000}
                rows={5}
                placeholder="What should your users know?"
              />
            </label>
            <button className="btn btn-primary" disabled={busy}>
              Preview announcement
            </button>
          </form>
          <div className="admin-delivery-note">
            <strong>Delivery overview</strong>
            <p>
              {overview?.push_pending ?? "—"} queued ·{" "}
              {overview?.push_failed ?? "—"} stopped after errors or unavailable
              devices
            </p>
            <small>
              Push acceptance does not confirm a user has read an update. The
              inbox remains available.
            </small>
          </div>
        </section>
      </div>
      <section className="mvp-panel audit-panel">
        <h2>Recent activity</h2>
        {overview?.recent_activity.map((item) => (
          <div className="audit-row" key={item.id}>
            <strong>
              {item.action.replaceAll(".", " · ").replaceAll("_", " ")}
            </strong>
            <span>{item.actor__email || "System"}</span>
            <time>{new Date(item.created_at).toLocaleString()}</time>
          </div>
        ))}
      </section>
      {(confirm || announcement) && (
        <ConfirmationDialog
          busy={busy}
          onClose={() => {
            setConfirm(null);
            setAnnouncement(null);
          }}
        >
          <h2 id="confirm-title">
            {confirm ? "Confirm account change" : "Preview announcement"}
          </h2>
          {confirm ? (
            <p>
              {confirm.action.replaceAll("_", " ")} for{" "}
              <strong>{confirm.user.email}</strong>?{" "}
              {confirm.action === "suspend" &&
                "This immediately blocks account access."}
            </p>
          ) : (
            <>
              <h3>{announcement?.title}</h3>
              <p className="announcement-preview">{announcement?.message}</p>
              <p>This will go to all active users.</p>
            </>
          )}
          <div className="button-row">
            <button
              className="btn btn-secondary"
              disabled={busy}
              autoFocus
              onClick={() => {
                setConfirm(null);
                setAnnouncement(null);
              }}
            >
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={confirm ? control : broadcast}
            >
              {busy
                ? "Saving…"
                : confirm
                  ? "Confirm change"
                  : "Send announcement"}
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
        </ConfirmationDialog>
      )}
    </>
  );
}
