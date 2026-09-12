"use client";

import { Bell, Bot, ClipboardList, CreditCard, FileSpreadsheet, LayoutDashboard, Link2, LogOut, ScanLine, Settings, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, clearTokens, hasSession } from "@/lib/api";
import type { User } from "@/lib/types";

const navigation = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/dashboard/digitize", label: "Digitize questionnaire", icon: UploadCloud },
  { href: "/dashboard/questionnaires", label: "My questionnaires", icon: ClipboardList },
  { href: "/dashboard/exports", label: "Exports", icon: FileSpreadsheet },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (!hasSession()) {
      router.replace("/login");
      return;
    }
    api<User>("/auth/me/").then(setUser).catch(() => { clearTokens(); router.replace("/login"); });
  }, [router]);

  function logout() {
    clearTokens();
    router.replace("/login");
  }

  if (!user) return <div className="loading-screen"><div className="spinner" aria-label="Loading" /></div>;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/dashboard"><span className="brand-mark"><ScanLine size={19} /></span> ScanToForms</Link>
        <div className="side-label">Workspace</div>
        <nav className="side-nav">
          {navigation.map(({ href, label, icon: Icon }) => <Link key={href} className={`side-link ${pathname === href || (href !== "/dashboard" && pathname.startsWith(href)) ? "active" : ""}`} href={href}><Icon size={16} /> {label}</Link>)}
        </nav>
        <div className="side-label">Tools</div>
        <nav className="side-nav">
          <Link className={`side-link ${pathname.startsWith("/dashboard/bot-lab") ? "active" : ""}`} href="/dashboard/bot-lab"><Bot size={16} /> Bot Lab <span className="nav-badge">Pro</span></Link>
          <Link className={`side-link ${pathname.startsWith("/dashboard/google-forms") ? "active" : ""}`} href="/dashboard/google-forms"><Link2 size={16} /> Google Forms <span className="nav-badge">Pro</span></Link>
          <Link className={`side-link ${pathname.startsWith("/dashboard/billing") ? "active" : ""}`} href="/dashboard/billing"><CreditCard size={16} /> Plans &amp; billing</Link>
          <Link className={`side-link ${pathname.startsWith("/dashboard/settings") ? "active" : ""}`} href="/dashboard/settings"><Settings size={16} /> Settings</Link>
        </nav>
        <div className="side-user"><span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span><div><strong>{user.name}</strong><span>{user.email}</span></div><button className="logout-btn" onClick={logout} aria-label="Log out"><LogOut size={15} /></button></div>
      </aside>
      <main className="app-main">
        <header className="topbar"><p>Private research workspace</p><div className="top-actions"><button className="icon-btn" aria-label="Notifications"><Bell size={16} /></button><Link className="btn btn-primary" href="/dashboard/digitize"><UploadCloud size={15} /> Digitize</Link></div></header>
        {children}
      </main>
    </div>
  );
}
