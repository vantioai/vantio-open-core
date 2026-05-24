"use client";
import { useState } from "react";

async function startTrial() {
  const res = await fetch("/api/stripe/create-checkout-session", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}),
  });
  const { url, error } = await res.json() as { url?: string; error?: string };
  if (url) window.location.href = url;
  else alert(error ?? "Failed to start checkout.");
}

const TIERS = [
  {
    label: "TIER 03", name: "Enterprise",
    price: "Custom", period: "ARR from $50k",
    desc: "Ring-0 eBPF Physical Containment. Sovereign VPC deployment. Kubernetes DaemonSet — no WSL, no proxies.",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    cta: "Request Access", href: "/enterprise", variant: "outline" as const,
    features: [
      "Ring-0 eBPF Physical Containment",
      "RISC Zero zkVM mathematical proofs",
      "Sub-millisecond Wave Function Collapse",
      "SAML 2.0 / Okta federation",
      "7-year WORM retention",
      "Dedicated support + onboarding",
    ],
  },
  {
    label: "TIER 02", name: "PRO / SMB", badge: "Most Popular",
    price: "$499", period: "/month",
    desc: "5–25ms transparent routing latency. Stripe self-serve payments. 30-day Spanner WORM log retention.",
    color: "text-blue-400", border: "border-blue-400/40", bg: "bg-blue-400/5",
    cta: "Start 14-Day Trial", href: "#", variant: "primary" as const,
    features: [
      "Transparent HTTPS interception",
      "5–25ms transparent routing latency",
      "30-day Spanner WORM log retention",
      "Multi-provider transparent routing",
      "Stripe self-serve payments",
      "Email support — 24hr SLA",
    ],
  },
  {
    label: "TIER 01", name: "Developer",
    price: "$0", period: "/month",
    desc: "Open-Core SDK. Frictionless npm install · pip install. 10,000 events/mo free.",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
    cta: "Start Free", href: "/developers", variant: "outline" as const,
    features: [
      "Node.js / TypeScript & Python SDK",
      "Frictionless npm install · pip install",
      "10,000 events / mo free",
      "Community SLA",
      "Open-source SDK on GitHub",
      "HMAC-signed telemetry",
    ],
  },
];

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-24">
      <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Pricing</p>
      <h1 className="mb-4 text-center text-4xl font-bold">Choose Your Containment Protocol</h1>
      <p className="mb-20 text-center text-[--muted]">Start free. Scale to sovereign.</p>

      <div className="grid gap-6 md:grid-cols-3">
        {TIERS.map((t) => (
          <div key={t.name} className={`relative flex flex-col rounded-xl border ${t.border} ${t.bg} p-8`}>
            {t.badge && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-400 px-3 py-0.5 text-xs font-bold text-black">
                {t.badge}
              </span>
            )}
            <p className={`mb-1 font-mono text-xs ${t.color}`}>{t.label}</p>
            <h2 className={`mb-1 text-2xl font-bold ${t.color}`}>{t.name}</h2>
            <p className="mb-4 text-xs text-[--muted]">{t.desc}</p>
            <div className="mb-6 flex items-end gap-1">
              <span className="text-4xl font-bold">{t.price}</span>
              <span className="mb-1 text-xs text-[--muted]">{t.period}</span>
            </div>
            {t.variant === "primary" ? (
              <button onClick={startTrial}
                className="mb-8 block w-full rounded-md bg-blue-400 py-3 text-sm font-semibold text-black transition-colors hover:bg-blue-300">
                {t.cta}
              </button>
            ) : (
              <a href={t.href}
                className={`mb-8 block w-full rounded-md border ${t.border} py-3 text-center text-sm font-semibold ${t.color} transition-colors hover:bg-white/5`}>
                {t.cta}
              </a>
            )}
            <ul className="flex-1 space-y-3">
              {t.features.map((f) => (
                <li key={f} className={`flex items-start gap-2 text-xs text-[--muted]`}>
                  <span className={t.color}>→</span> {f}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <p className="mt-12 text-center text-sm text-[--muted]">
        Start with the Developer SDK — zero risk, no credit card. Upgrade to Managed Proxy when you need active
        blocking. Contact Enterprise Sales for sovereign deployment.
      </p>
    </main>
  );
}
