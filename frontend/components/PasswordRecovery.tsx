"use client";
import Link from "next/link";
import { useState } from "react";
import { api, clearTokens } from "@/lib/api";
export default function PasswordRecovery({
  confirm = false,
}: {
  confirm?: boolean;
}) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <main className="mvp-content auth-recovery">
      <Link href="/">ScanToForms</Link>
      <h1>{confirm ? "Choose a new password" : "Reset your password"}</h1>
      <form
        className="form-stack"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const params = new URLSearchParams(window.location.search);
            const result = await api<{ detail: string }>(
              `/auth/password-reset/${confirm ? "confirm/" : ""}`,
              {
                auth: false,
                method: "POST",
                body: JSON.stringify(
                  confirm
                    ? {
                        uid: params.get("uid"),
                        token: params.get("token"),
                        password,
                      }
                    : { email },
                ),
              },
            );
            setMessage(result.detail);
            if (confirm) clearTokens();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Request failed.");
          } finally {
            setBusy(false);
          }
        }}
      >
        {confirm ? (
          <label className="field">
            New password
            <input
              type="password"
              required
              minLength={10}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
        ) : (
          <label className="field">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
        )}
        <button className="btn btn-primary" disabled={busy}>
          {confirm ? "Save new password" : "Send reset instructions"}
        </button>
        {error && <p role="alert">{error}</p>}
        {message && <p role="status">{message}</p>}
      </form>
      <p>
        <Link href="/login">Back to login</Link>
      </p>
    </main>
  );
}
