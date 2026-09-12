"use client";

import { Check, CreditCard, Plus, Users } from "lucide-react";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { BillingSummary, PaymentTransaction, Plan } from "@/lib/types";

const money = (kobo: number) => new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(kobo / 100);

export default function BillingPage() {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [summary, setSummary] = useState<BillingSummary | null>(null);
  const [cycle, setCycle] = useState<"MONTHLY" | "YEARLY">("MONTHLY");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api<Plan[]>("/billing/plans/", { auth: false }), api<BillingSummary>("/billing/summary/")])
      .then(([catalogue, account]) => { setPlans(catalogue); setSummary(account); })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Billing could not be loaded."));
  }, []);

  async function checkout(product: "SUBSCRIPTION" | "EXTRA_PAGES", plan?: Plan) {
    setBusy(plan?.code ?? product); setError("");
    try {
      const payment = await api<PaymentTransaction>("/billing/checkout/", {
        method: "POST",
        body: JSON.stringify({ product, plan_code: plan?.code, billing_cycle: plan ? cycle : undefined }),
      });
      window.location.assign(payment.authorization_url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Checkout could not be started.");
      setBusy("");
    }
  }

  if (!summary) return <div className="loading-screen"><div className="spinner" /></div>;
  const usagePercent = Math.min(100, Math.round((summary.usage.pages_used / Math.max(summary.usage.included_pages + summary.usage.extra_pages, 1)) * 100));

  return <div className="page-content billing-page">
    <header className="page-header"><div><h1>Plans &amp; billing</h1><p>Simple monthly limits, secure Paystack checkout and no unlimited-use surprises.</p></div></header>
    {error && <div className="form-error" role="alert">{error}</div>}
    <section className="usage-card">
      <div><span className="section-kicker">Current plan</span><h2>{summary.plan.name}</h2><p>{summary.usage.pages_remaining} OCR pages remaining this month</p></div>
      <div className="usage-meter"><div><span>{summary.usage.pages_used} used</span><span>{summary.usage.included_pages + summary.usage.extra_pages} available</span></div><div className="progress-track"><div className="progress-fill" style={{ width: `${usagePercent}%` }} /></div></div>
      <button className="btn btn-dark" disabled={busy === "EXTRA_PAGES" || !summary.paystack_configured} onClick={() => checkout("EXTRA_PAGES")}><Plus size={15} /> Buy 100 pages — ₦1,500</button>
    </section>
    {!summary.paystack_configured && <div className="billing-notice">Paystack test/live keys still need to be added by the administrator before checkout can open.</div>}
    <div className="billing-toggle"><button className={cycle === "MONTHLY" ? "active" : ""} onClick={() => setCycle("MONTHLY")}>Monthly</button><button className={cycle === "YEARLY" ? "active" : ""} onClick={() => setCycle("YEARLY")}>Yearly · 2 months free</button></div>
    <section className="pricing-grid">
      {plans.map((plan) => {
        const current = summary.plan.code === plan.code;
        const amount = cycle === "YEARLY" ? plan.yearly_price_kobo : plan.monthly_price_kobo;
        return <article className={`pricing-card ${plan.code === "STUDENT" ? "featured" : ""}`} key={plan.code}>
          <div className="pricing-card-head">{plan.max_team_members > 1 ? <Users size={20} /> : <CreditCard size={20} />}<span>{plan.name}</span></div>
          <p>{plan.description}</p>
          <div className="price">{plan.code === "ORGANIZATION" ? "From " : ""}{money(amount ?? 0)}<small>/{cycle === "YEARLY" ? "year" : "month"}</small></div>
          <ul>{plan.features.map((feature) => <li key={feature}><Check size={14} /> {feature}</li>)}</ul>
          {plan.code === "FREE" ? <button className="btn btn-ghost" disabled>{current ? "Current plan" : "Free plan"}</button> : <button className="btn btn-primary" disabled={current || Boolean(busy) || !summary.paystack_configured} onClick={() => checkout("SUBSCRIPTION", plan)}>{current ? "Current plan" : busy === plan.code ? "Opening Paystack…" : plan.code === "ORGANIZATION" ? "Start organization plan" : "Choose plan"}</button>}
        </article>;
      })}
    </section>
    <p className="form-note" style={{ marginTop: 16 }}>Organization members are added by the administrator. Contact <a href={`mailto:${summary.admin_contact_email}?subject=Organization members`}>{summary.admin_contact_email}</a> after payment to set up the team.</p>
  </div>;
}
