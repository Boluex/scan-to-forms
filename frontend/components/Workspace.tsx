"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { api, hasSession, logout } from "@/lib/api";
import type { User } from "@/lib/types";
const UserContext = createContext<User | null>(null);
export const useUser = () => useContext(UserContext);
export default function Workspace({
  children,
  operatorOnly = false,
}: {
  children: React.ReactNode;
  operatorOnly?: boolean;
}) {
  const [user, setUser] = useState<User | null>(null);
  const [unread, setUnread] = useState(0);
  const router = useRouter();
  const path = usePathname();
  useEffect(() => {
    if (!hasSession()) {
      router.replace(`/login?next=${encodeURIComponent(path)}`);
      return;
    }
    api<User>("/auth/me/")
      .then((value) => {
        if (operatorOnly && !value.is_staff) router.replace("/orders");
        else setUser(value);
      })
      .catch(() => router.replace("/login"));
  }, [router, path, operatorOnly]);
  useEffect(() => {
    if (!user) return;
    const load = () =>
      api<{ count: number }>("/notifications/unread-count/")
        .then((data) => setUnread(data.count))
        .catch(() => undefined);
    load();
    const timer = setInterval(load, 30000);
    window.addEventListener("notifications-updated", load);
    return () => {
      clearInterval(timer);
      window.removeEventListener("notifications-updated", load);
    };
  }, [user]);
  if (!user)
    return (
      <div className="loading-screen" role="status">
        Loading your workspace…
      </div>
    );
  return (
    <UserContext.Provider value={user}>
      <div className="mvp-shell">
        <header className="mvp-nav">
          <Link href="/" className="brand">
            ScanToForms
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/">Home</Link>
            <Link href="/digitize">Digitize Questionnaire</Link>
            <Link href="/synthetic">Synthetic Test Data</Link>
            <Link href="/orders">
              {user.is_staff ? "Orders / Operator" : "My Orders"}
            </Link>
            <Link href="/notifications">
              Notifications{" "}
              <span aria-label="Unread notifications">({unread})</span>
            </Link>
            <Link href="/account">Account</Link>
          </nav>
          <button
            className="btn btn-ghost"
            onClick={async () => {
              try {
                await logout();
              } finally {
                router.replace("/login");
              }
            }}
          >
            Log out
          </button>
        </header>
        {user.is_staff && (
          <div className="operator-banner">
            Operator workspace · Changes and payment verification are audited.
          </div>
        )}
        <main className="mvp-content">{children}</main>
      </div>
    </UserContext.Provider>
  );
}
