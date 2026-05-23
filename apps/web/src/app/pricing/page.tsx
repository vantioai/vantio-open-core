"use client";
import type { Metadata } from "next";
import Link from "next/link";
import { useState } from "react";

// Metadata must be in a separate server component when using "use client".
// Moved to layout or a wrapper — keeping title here for reference only.

async function redirectToCheckout() {
  const res = await fetch("/api/stripe/create-checkout-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await res.json() as { url?: string; error?: string };
  if (data.url) {
    window.location.href = data.url;
  } else {
    alert(data.error ?? "Failed to start checkout.");
  }
}

const tiers = [
  {
    name: "Open-Core",
    badge: "FREE",
    price: "$0",
    period: "forever",
    description:
      "For individual developers and open-source projects. Full SDK access, no credit card required.",
    cta: "Get the SDK",
    ctaHref: "https://github.com",
    ctaVariant: "secondary" as const,
    highlighted: false,
    features: [
      "@vantio/agent-sdk (MIT license)",
      "withVantio() async context tracing",
      "VANTIO_TRACE_ID propagation",
      "Console-level anomaly output",
      "Community support",
    ],
    limitations: [
      "No TrueTime Ledger retention",
      "No Audit Mode (VANTIO_AUDIT_MODE)",
      "No team dashboard",
    ],
  },
  {
    name: "SMB",
    badge: "PRO",
    price: "$499",
    period: "per month",
    description:
      "For small and mid-size businesses deploying LLM agents in production. Full kernel-level enforcement.",
    cta: "Start Free Trial",
    ctaHref: "/api/stripe/create-checkout-session",
    ctaVariant: "primary" as const,
    highlighted: true,
    features: [
      "Everything in Open-Core",
      "eBPF Phantom Engine (Ring-0 enforcement)",
      "Pinned trace map at /sys/fs/bpf/vantio_trace_map",
      "VANTIO_AUDIT_MODE (zero-risk deployment)",
      "TrueTime Ledger — 90-day retention",
      "Supabase-backed tenant dashboard",
      "Stripe self-serve billing",
      "Email support (< 24h SLA)",
      "Up to 10 seats",
    ],
    limitations: [],
  },
  {
    name: "Enterprise",
    badge: "CUSTOM",
    price: "Custom",
    period: "annual contract",
    description:
      "For Fortune 500 and regulated institutions requiring dedicated infrastructure and compliance guarantees.",
    cta: "Contact Sales",
    ctaHref: "/auth/enterprise",
    ctaVariant: "secondary" as const,
    highlighted: false,
    features: [
      "Everything in SMB",
      "SAML / SSO (Okta, Azure AD, Google Workspace)",
      "Dedicated GCP Spanner instance",
      "TrueTime Ledger — unlimited WORM retention",
      "SOC 2 Type II report access",
      "ISO 27001 / NIST CSF compliance mapping",
      "SLSA Level 3 supply-chain attestation",
      "Dedicated Slack channel + CSM",
      "Unlimited seats",
      "Custom SLA (99.99% uptime)",
    ],
    limitations: [],
  },
];

export default function PricingPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Header */}
      <section className="mx-auto max-w-5xl px-6 pb-12 pt-20 text-center">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-gray-400">
          Vantio AI — Pricing
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-gray-900 sm:text-5xl">
          Deterministic AI Governance,
          <br />
          <span className="text-gray-500">at every scale.</span>
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-gray-500">
          From an open-source SDK for developers to a kernel-enforced eBPF
          containment layer for Fortune 500 institutions. One architecture,
          three deployment tiers.
        </p>
      </section>

      {/* Tier cards */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid gap-8 lg:grid-cols-3">
          {tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative flex flex-col rounded-2xl border p-8 ${
                tier.highlighted
                  ? "border-gray-900 bg-gray-900 text-white shadow-2xl"
                  : "border-gray-200 bg-white text-gray-900"
              }`}
            >
              {tier.highlighted && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-white px-4 py-1 text-xs font-bold uppercase tracking-widest text-gray-900 shadow">
                    Most Popular
                  </span>
                </div>
              )}

              {/* Tier header */}
              <div className="mb-6">
                <div className="mb-2 flex items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-bold uppercase tracking-widest ${
                      tier.highlighted
                        ? "bg-white/15 text-white"
                        : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {tier.badge}
                  </span>
                  <span
                    className={`text-sm font-semibold ${tier.highlighted ? "text-gray-300" : "text-gray-400"}`}
                  >
                    {tier.name}
                  </span>
                </div>
                <div className="flex items-end gap-1">
                  <span className="text-4xl font-bold">{tier.price}</span>
                  {tier.price !== "Custom" && (
                    <span
                      className={`mb-1 text-sm ${tier.highlighted ? "text-gray-400" : "text-gray-400"}`}
                    >
                      / {tier.period}
                    </span>
                  )}
                </div>
                <p
                  className={`mt-3 text-sm leading-relaxed ${tier.highlighted ? "text-gray-300" : "text-gray-500"}`}
                >
                  {tier.description}
                </p>
              </div>

              {/* CTA */}
              {tier.ctaVariant === "primary" ? (
                <button
                  onClick={redirectToCheckout}
                  className="mb-8 inline-flex w-full items-center justify-center rounded-lg bg-white px-5 py-3 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-100"
                >
                  {tier.cta}
                </button>
              ) : (
                <Link
                  href={tier.ctaHref}
                  className={`mb-8 inline-flex w-full items-center justify-center rounded-lg px-5 py-3 text-sm font-semibold transition-colors ${
                    tier.highlighted
                      ? "border border-white/30 text-white hover:bg-white/10"
                      : "border border-gray-300 text-gray-700 hover:bg-gray-50"
                  }`}
                >
                  {tier.cta}
                </Link>
              )}

              {/* Features */}
              <ul className="flex-1 space-y-3">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm">
                    <span
                      className={`mt-0.5 flex-shrink-0 ${tier.highlighted ? "text-green-400" : "text-green-600"}`}
                    >
                      ✓
                    </span>
                    <span
                      className={tier.highlighted ? "text-gray-200" : "text-gray-600"}
                    >
                      {f}
                    </span>
                  </li>
                ))}
                {tier.limitations.map((l) => (
                  <li key={l} className="flex items-start gap-2 text-sm">
                    <span className="mt-0.5 flex-shrink-0 text-gray-400">✗</span>
                    <span className="text-gray-400">{l}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* SMB flow callout */}
      <section className="border-t border-gray-100 bg-gray-50 px-6 py-16">
        <div className="mx-auto max-w-3xl">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-400">
            SMB Onboarding Flow
          </h2>
          <h3 className="mb-8 text-2xl font-bold text-gray-900">
            From checkout to kernel enforcement in under 5 minutes.
          </h3>
          <ol className="space-y-6">
            {[
              {
                step: "01",
                title: "Stripe Checkout",
                body: "Click "Start Free Trial." Stripe Checkout collects payment and fires a checkout.session.completed webhook.",
              },
              {
                step: "02",
                title: "Tenant Provisioned (Supabase)",
                body: "The webhook handler upserts your account in the tenants table — tier set to PRO, stripe_subscription_id stored.",
              },
              {
                step: "03",
                title: "Install the Phantom Engine (WSL)",
                body: "sudo ./vantio-loader starts the eBPF programs, pins the trace map at /sys/fs/bpf/vantio_trace_map, and begins enforcing.",
              },
              {
                step: "04",
                title: "Wrap Your Agent",
                body: "Add withVantio() from @vantio/agent-sdk around your LLM agent call. The VANTIO_TRACE_ID flows from Ring-3 to Ring-0 automatically.",
              },
              {
                step: "05",
                title: "Anomalies Surface in Your Dashboard",
                body: "Every intercepted SSL_write attempt is recorded to the TrueTime Ledger and visible in your SMB dashboard — no Kubernetes required.",
              },
            ].map(({ step, title, body }) => (
              <li key={step} className="flex gap-5">
                <span className="mt-0.5 flex-shrink-0 font-mono text-xs font-bold text-gray-300">
                  {step}
                </span>
                <div>
                  <p className="font-semibold text-gray-900">{title}</p>
                  <p className="mt-1 text-sm text-gray-500">{body}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="mt-10">
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-2 rounded-lg bg-gray-900 px-6 py-3 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
            >
              Preview SMB Dashboard →
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
