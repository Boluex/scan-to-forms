"use client";

import { ScanLine, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { api, setTokens } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password"));
    if (password !== form.get("passwordConfirm")) {
      setError("Passwords do not match.");
      setBusy(false);
      return;
    }
    try {
      await api("/auth/register/", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email: form.get("email"), name: form.get("name"), institution: form.get("institution"), password }),
      });
      const tokens = await api<{ access: string; refresh: string }>("/auth/login/", {
        method: "POST", auth: false, body: JSON.stringify({ email: form.get("email"), password }),
      });
      setTokens(tokens.access, tokens.refresh);
      router.replace("/orders");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create your account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-panel">
        <Link className="brand" href="/"><span className="brand-mark"><ScanLine size={20} /></span> ScanToForms</Link>
        <div className="auth-form-wrap">
          <h1>Start scanning.</h1>
          <p>Create your free research workspace. Track your orders and securely retrieve reviewed results.</p>
          <form className="form-stack" onSubmit={submit}>
            {error && <div className="form-error" role="alert">{error}</div>}
            <div className="field"><label htmlFor="name">Full name</label><input id="name" name="name" autoComplete="name" required /></div>
            <div className="field"><label htmlFor="email">Email address</label><input id="email" name="email" type="email" autoComplete="email" required /></div>
            <div className="field"><label htmlFor="institution">Institution <span className="form-note">(optional)</span></label><input id="institution" name="institution" autoComplete="organization" /></div>
            <div className="form-row">
              <div className="field"><label htmlFor="password">Password</label><input id="password" name="password" type="password" minLength={10} autoComplete="new-password" required /></div>
              <div className="field"><label htmlFor="passwordConfirm">Confirm password</label><input id="passwordConfirm" name="passwordConfirm" type="password" minLength={10} autoComplete="new-password" required /></div>
            </div>
            <span className="form-note">Use at least 10 characters and avoid common passwords.</span>
            <button className="btn btn-primary btn-large auth-submit" disabled={busy}>{busy ? "Creating workspace…" : "Create free account"}</button>
          </form>
          <p className="auth-switch">Already have an account? <Link href="/login">Log in</Link></p>
        </div>
      </section>
      <aside className="auth-side"><div className="auth-quote"><Sparkles size={34} /><blockquote>“I have 300 paper questionnaires.”<br />Now that sentence has a solution.</blockquote><p>Upload · Extract · Review · Export</p></div></aside>
    </main>
  );
}

