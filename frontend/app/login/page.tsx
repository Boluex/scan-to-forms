"use client";

import { ScanLine, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api, setTokens } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const tokens = await api<{ access: string; refresh: string }>("/auth/login/", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email: form.get("email"), password: form.get("password") }),
      });
      setTokens(tokens.access, tokens.refresh);
      router.replace("/orders");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to log in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Link className="brand" href="/"><span className="brand-mark"><ScanLine size={20} /></span> ScanToForms</Link>
        <div className="auth-form-wrap">
          <h1>Welcome back.</h1>
          <p>Continue turning your questionnaire backlog into usable data.</p>
          <form className="form-stack" onSubmit={submit}>
            {error && <div className="form-error" role="alert">{error}</div>}
            <div className="field"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required /></div>
            <div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required /></div>
            <button className="btn btn-primary btn-large auth-submit" disabled={busy}>{busy ? "Signing in…" : "Log in"}</button>
          </form>
          <p><Link href="/forgot-password">Forgot your password?</Link></p><p className="auth-switch">New here? <Link href="/register">Create a free account</Link></p>
        </div>
      </section>
      <aside className="auth-side"><div className="auth-quote"><ShieldCheck size={34} /><blockquote>Your questionnaires. Reviewed responses. An Apps Script for your form.</blockquote><p>Private uploads · Human review · Controlled beta</p></div></aside>
    </main>
  );
}

