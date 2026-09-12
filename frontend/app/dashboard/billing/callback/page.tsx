"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { api } from "@/lib/api";
import type { PaymentTransaction } from "@/lib/types";

function PaymentResult() {
  const params = useSearchParams();
  const [state, setState] = useState<"checking" | "success" | "failed">("checking");
  const [message, setMessage] = useState("Confirming your payment with Paystack…");
  useEffect(() => {
    const reference = params.get("reference") ?? params.get("trxref");
    if (!reference) { setState("failed"); setMessage("The payment reference is missing."); return; }
    api<PaymentTransaction>("/billing/verify/", { method: "POST", body: JSON.stringify({ reference }) })
      .then(() => { setState("success"); setMessage("Payment verified. Your allowance has been updated."); })
      .catch((caught) => { setState("failed"); setMessage(caught instanceof Error ? caught.message : "Payment could not be verified."); });
  }, [params]);
  return <div className="payment-result">{state === "checking" ? <div className="spinner" /> : state === "success" ? <CheckCircle2 size={42} /> : <XCircle size={42} />}<h1>{state === "success" ? "Payment complete" : state === "failed" ? "Payment not confirmed" : "Checking payment"}</h1><p>{message}</p><Link className="btn btn-primary" href="/dashboard/billing">Return to billing</Link></div>;
}

export default function BillingCallbackPage() { return <Suspense fallback={<div className="loading-screen"><div className="spinner" /></div>}><PaymentResult /></Suspense>; }
