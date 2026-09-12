"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Plan } from "@/lib/types";

const money = (kobo: number) => new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(kobo / 100);

export default function PricingPreview() {
  const [plans, setPlans] = useState<Plan[]>([]);
  useEffect(() => { api<Plan[]>("/billing/plans/", { auth: false }).then(setPlans).catch(() => undefined); }, []);
  if (!plans.length) return null;
  return <section className="public-pricing shell" id="pricing"><div className="section-kicker">Plans that grow with the work</div><div className="section-heading"><h2>Start free. Pay for heavier research.</h2><p>Every plan keeps human review at the centre. Extra OCR pages are ₦1,500 per 100 pages.</p></div><div className="pricing-grid">{plans.map((plan) => <article className={`pricing-card ${plan.code === "STUDENT" ? "featured" : ""}`} key={plan.code}><div className="pricing-card-head"><span>{plan.name}</span></div><p>{plan.description}</p><div className="price">{plan.code === "ORGANIZATION" ? "From " : ""}{money(plan.monthly_price_kobo)}<small>/month</small></div><ul>{plan.features.slice(0, 5).map((feature) => <li key={feature}><Check size={14} /> {feature}</li>)}</ul><Link className={plan.code === "FREE" ? "btn btn-ghost" : "btn btn-primary"} href="/register">{plan.code === "FREE" ? "Start free" : "Choose plan"}</Link></article>)}</div></section>;
}
