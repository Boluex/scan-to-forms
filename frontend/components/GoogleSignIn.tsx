"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { api, setTokens, signInDestination } from "@/lib/api";
import { googleConfigured, googleIdToken } from "@/lib/firebase";
export default function GoogleSignIn({ link = false }: { link?: boolean }) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const router = useRouter();
  if (!googleConfigured) return null;
  async function signIn() {
    setBusy(true);
    setMessage("");
    try {
      const id_token = await googleIdToken();
      if (link) {
        const result = await api<{ detail: string }>("/auth/google/link/", {
          method: "POST",
          body: JSON.stringify({ id_token }),
        });
        setMessage(result.detail);
      } else {
        const result = await api<{ access: string; refresh: string }>(
          "/auth/google/",
          { method: "POST", auth: false, body: JSON.stringify({ id_token }) },
        );
        setTokens(result.access, result.refresh);
        router.replace(signInDestination());
      }
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Google sign-in failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="google-signin">
      <button
        type="button"
        className="btn btn-secondary"
        disabled={busy}
        onClick={signIn}
      >
        <span className="google-g" aria-hidden="true">
          G
        </span>
        {busy
          ? "Connecting…"
          : link
            ? "Link Google account"
            : "Continue with Google"}
      </button>
      {message && <p role="status">{message}</p>}
    </div>
  );
}
