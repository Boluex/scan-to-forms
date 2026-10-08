"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import {
  ScanLine,
  Files,
  FlaskConical,
  Bell,
  Settings,
  ShieldCheck,
  LogOut,
  Menu,
  X,
  ArrowUpRight,
  Plus,
} from "lucide-react";
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
  const [user, setUser] = useState<User | null>(null),
    [unread, setUnread] = useState(0),
    [menu, setMenu] = useState(false),
    [error, setError] = useState("");
  const router = useRouter(),
    path = usePathname();
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
      .catch(() => {
        if (navigator.onLine) router.replace("/login");
        else setError("You’re offline. Reconnect to open your workspace.");
      });
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
    // Refresh an existing device registration without prompting for permission.
    import("@/lib/push").then(({ pushEnabled, enablePush }) => {
      if (pushEnabled()) void enablePush(false).catch(() => undefined);
    });
    return () => {
      clearInterval(timer);
      window.removeEventListener("notifications-updated", load);
    };
  }, [user]);
  if (!user)
    return (
      <div className="loading-screen" role="status">
        {error || "Opening your workspace…"}
      </div>
    );
  const admin = user.is_staff && (user.is_superuser || user.role === "ADMIN");
  const links = [
    {
      href: "/orders",
      label: user.is_staff ? "Customer orders" : "My orders",
      icon: Files,
    },
    { href: "/digitize", label: "Digitize Questionnaire", icon: ScanLine },
    { href: "/synthetic", label: "Synthetic Test Data", icon: FlaskConical },
    { href: "/notifications", label: "Notifications", icon: Bell },
    { href: "/account", label: "Account settings", icon: Settings },
  ];
  const title =
    links.find((link) => path.startsWith(link.href))?.label ||
    (path.startsWith("/admin") ? "Administration" : "Operator tools");
  return (
    <UserContext.Provider value={user}>
      <div className="workspace-shell">
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <div className="mobile-top">
          <Link href="/orders" className="brand">
            <ScanLine size={24} /> ScanToForms
          </Link>
          <button
            className="icon-btn"
            aria-label={menu ? "Close navigation" : "Open navigation"}
            aria-expanded={menu}
            aria-controls="workspace-sidebar"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X /> : <Menu />}
          </button>
        </div>
        <aside
          id="workspace-sidebar"
          className={`workspace-sidebar ${menu ? "is-open" : ""}`}
        >
          <Link href="/" className="brand">
            <span className="brand-mark">
              <ScanLine size={21} />
            </span>
            ScanToForms
          </Link>
          <p className="workspace-caption">Your research, organised.</p>
          <Link
            href="/digitize"
            className="btn btn-primary new-project"
            onClick={() => setMenu(false)}
          >
            <Plus size={17} /> New project
          </Link>
          <p className="nav-section-label">Workspace</p>
          <nav aria-label="Main navigation">
            {links.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={`workspace-link ${path.startsWith(href) ? "active" : ""}`}
                aria-current={path.startsWith(href) ? "page" : undefined}
                onClick={() => setMenu(false)}
              >
                <Icon size={19} />
                <span>{label}</span>
                {href === "/notifications" && unread > 0 && (
                  <span className="unread-badge">{unread}</span>
                )}
              </Link>
            ))}
            {admin && (
              <Link
                href="/admin"
                className={`workspace-link ${path.startsWith("/admin") ? "active" : ""}`}
                onClick={() => setMenu(false)}
              >
                <ShieldCheck size={19} />
                Admin dashboard
              </Link>
            )}
            {user.is_staff && (
              <Link
                className="workspace-link"
                href="/dashboard/questionnaires"
                onClick={() => setMenu(false)}
              >
                <Files size={19} />
                Review tools
              </Link>
            )}
          </nav>
          <div className="sidebar-bottom">
            <div className="sidebar-note">
              <strong>From paper to progress.</strong>
              <p>
                Keep each respondent’s pages together for a smoother review.
              </p>
              <Link href="/">
                How it works <ArrowUpRight size={14} />
              </Link>
            </div>
            <div className="profile-row">
              <span className="profile-avatar">
                {user.name.charAt(0).toUpperCase()}
              </span>
              <div>
                <strong>{user.name}</strong>
                <small>
                  {user.is_staff ? "Operator workspace" : "Research workspace"}
                </small>
              </div>
            </div>
            <button
              className="workspace-link logout-control"
              onClick={async () => {
                try {
                  await logout();
                } finally {
                  router.replace("/login");
                }
              }}
            >
              <LogOut size={17} />
              Log out
            </button>
          </div>
        </aside>
        <div className="workspace-main">
          <header className="workspace-topbar">
            <span>
              Workspace <span className="breadcrumb-divider">/</span>{" "}
              <strong>{title}</strong>
            </span>
            <div>
              <span className="beta-label">BETA</span>
              <Link
                href="/notifications"
                className="icon-btn"
                aria-label="Open inbox"
              >
                <Bell size={18} />
                {unread > 0 && <i className="notification-dot" />}
              </Link>
            </div>
          </header>
          <main id="main-content" className="mvp-content workspace-content">
            {children}
          </main>
          <footer className="workspace-footer">
            ScanToForms <span>Built for thoughtful research.</span>
          </footer>
        </div>
      </div>
    </UserContext.Provider>
  );
}
