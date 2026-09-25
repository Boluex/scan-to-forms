"use client";

import { FormEvent, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { User } from "@/lib/types";

export default function SettingsPage() {
  const [user, setUser] = useState<User | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => { api<User>("/auth/me/").then(setUser).catch(e => setError(e.message)); }, []);
  async function save(event: FormEvent<HTMLFormElement>) { event.preventDefault(); setError(""); try { const form = new FormData(event.currentTarget); const updated = await api<User>("/auth/me/", { method: "PATCH", body: JSON.stringify({ name: form.get("name"), institution: form.get("institution") }) }); setUser(updated); setMessage("Profile saved."); } catch(e) {setError(e instanceof Error ? e.message : "Unable to save profile.");} }
  if (!user && error) return <p role="alert">{error}</p>;
  if (!user) return <div className="loading-screen"><div className="spinner" /></div>;
  return <div className="page-content"><header className="page-header"><div><h1>Account settings</h1><p>Manage your identity and research context.</p></div></header><section className="panel" style={{ padding: 28, maxWidth: 680 }}>{error && <p role="alert">{error}</p>}{message && <div className="form-success">{message}</div>}<form className="form-stack" onSubmit={save}><div className="field"><label>Email</label><input value={user.email} disabled /></div><div className="field"><label htmlFor="name">Full name</label><input id="name" name="name" defaultValue={user.name} required /></div><div className="field"><label htmlFor="institution">Institution</label><input id="institution" name="institution" defaultValue={user.institution} /></div><div className="field"><label>Account role</label><input value={user.role.replaceAll("_", " ").toLowerCase()} disabled /></div><div><button className="btn btn-primary">Save changes</button></div></form></section></div>;
}

