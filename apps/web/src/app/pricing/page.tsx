"use client";

import { PRICING_FAQ } from "@/lib/faq";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";
import { RoiStrip } from "@/components/roi-strip";

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
    label: "DEVELOPER", name: "Free",
    for: "For individuals and open-source projects.",
    price: "$0", period: "forever",
    color: "text-[var(--accent)]", border: "border-[var(--accent)]/30", bg: "bg-[var(--accent)]/5",
    cta: "Get Started Free", href: "/developers",
    features: [
      { text: "See every action your AI agents take", strong: true },
      { text: "10,000 events per month included" },
      { text: "Works with Node.js and Python" },
      { text: "Real-time activity dashboard" },
      { text: "Open-source on GitHub" },
      { text: "Community support" },
    ],
  },
  {
    label: "Pro", name: "Pro", badge: "Most Popular",
    for: "For teams deploying AI in production.",
    price: "$499", period: "/month",
    color: "text-blue-400", border: "border-blue-400/40", bg: "bg-blue-400/5",
    cta: "Start 14-Day Free Trial", href: "#",
    features: [
      { text: "Automatic PII redaction before data leaves your app", strong: true },
      { text: "Spend caps & host allow/block policy enforcement" },
      { text: "Full tamper-proof audit trail of every action" },
      { text: "Anonymized benchmarks vs. industry peers" },
      { text: "Works with any AI framework — Node.js & Python" },
      { text: "Slack alerts + 24-hour email support" },
    ],
  },
  {
    label: "ENTERPRISE", name: "Enterprise",
    for: "For regulated industries and large teams.",
    price: "Custom", period: "from $50k/year",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    cta: "Talk to Sales", href: "/enterprise",
    features: [
      { text: "Start in audit mode — observe everything, block nothing, zero risk", strong: true },
      { text: "Kernel-level (eBPF) enforcement for the workloads you enroll" },
      { text: "Runs inside your own cloud — your data never leaves your walls" },
      { text: "7-year tamper-proof audit records" },
      { text: "SAML / Okta single sign-on" },
      { text: "Dedicated support + engineering onboarding" },
      { text: "SOC 2, MiFID II, HIPAA, GDPR compliance ready" },
    ],
  },
];

const PRICING_STATS = [
  {
    metric: "~80%",
    label: "of enterprises have no mature AI governance",
    source: "Deloitte, 2026",
  },
  {
    metric: "97%",
    label: "of AI breaches had zero access controls",
    source: "IBM / Ponemon, 2025",
  },
  {
    metric: "+$670K",
    label: "added to breaches by ungoverned AI",
    source: "IBM / Ponemon, 2025",
  },
] as const;

export default function PricingPage() {
  return (
    <main>
      {/* ── Intro ──────────────────────────────────────────────────────────── */}
      <div className="mx-auto max-w-6xl px-6 pb-10 pt-24">
        <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Pricing</p>
        <h1 className="mb-3 text-center text-4xl font-bold">Simple, honest pricing.</h1>
        <p className="mb-10 text-center text-[var(--muted)]">
          Start free. No credit card. Upgrade when you need active enforcement or enterprise controls.
        </p>

        {/* Compact risk stats — the governance gap */}
        <div className="mb-0 grid grid-cols-1 gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 sm:grid-cols-3">
          {PRICING_STATS.map((s) => (
            <div key={s.metric} className="flex items-center gap-4 rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-4 py-3">
              <span className="shrink-0 bg-gradient-to-r from-[var(--accent)] via-emerald-300 to-[var(--accent)] bg-clip-text text-3xl font-black leading-none text-transparent">
                {s.metric}
              </span>
              <div>
                <p className="text-xs font-medium leading-snug text-[var(--foreground)]">{s.label}</p>
                <p className="mt-0.5 text-[10px] text-[var(--muted)]/60">{s.source}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── ROI strip — what governance delivers ───────────────────────────── */}
      <RoiStrip />

      {/* ── Tier cards + FAQ ───────────────────────────────────────────────── */}
      <div className="mx-auto max-w-6xl px-6 pb-24 pt-14">
        <div className="grid gap-6 md:grid-cols-3 md:items-stretch">
          {TIERS.map((t) => (
            <div key={t.name} className={`relative flex h-full flex-col rounded-xl border ${t.border} ${t.bg} p-8`}>
              {t.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-400 px-3 py-0.5 text-xs font-bold text-black">
                  {t.badge}
                </span>
              )}
              <p className={`mb-1 text-xs font-semibold uppercase tracking-widest ${t.color}`}>{t.label}</p>
              <h2 className="mb-1 text-2xl font-bold">{t.name}</h2>
              <p className="mb-5 text-sm text-[var(--muted)]">{t.for}</p>
              {t.href === "#" && isTier2Waitlist() && (
                <span className="mb-4 inline-flex w-fit items-center rounded-full border border-blue-400/30 bg-blue-400/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
                  Launching soon
                </span>
              )}

              <ul className="flex-1 space-y-3">
                {t.features.map((f) => (
                  <li key={f.text} className="flex items-start gap-2 text-sm">
                    <span className={`mt-0.5 shrink-0 ${t.color}`}>→</span>
                    <span className={f.strong ? "font-medium text-[var(--foreground)]" : "text-[var(--muted)]"}>{f.text}</span>
                  </li>
                ))}
              </ul>

              <div className="mt-auto pt-6">
                <div className="mb-4 flex items-end gap-1">
                  <span className="text-4xl font-bold">{t.price}</span>
                  <span className="mb-1 text-xs text-[var(--muted)]">{t.period}</span>
                </div>

                {t.href === "#" && isTier2Waitlist() ? (
                  <WaitlistCta
                    source="pricing"
                    wrapperClassName=""
                    buttonClassName="w-full rounded-md bg-blue-400 py-3 text-sm font-semibold text-black transition-colors hover:bg-blue-300"
                  />
                ) : t.href === "#" ? (
                  <button onClick={startTrial}
                    className="w-full rounded-md bg-blue-400 py-3 text-sm font-semibold text-black transition-colors hover:bg-blue-300">
                    {t.cta}
                  </button>
                ) : (
                  <a href={t.href}
                    className={`block w-full rounded-md border ${t.border} py-3 text-center text-sm font-semibold ${t.color} transition-colors hover:bg-white/5`}>
                    {t.cta}
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-20">
          <h2 className="mb-8 text-xl font-bold">Common questions</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {PRICING_FAQ.map(({ question, answer }) => (
              <div key={question} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
                <p className="mb-2 font-semibold">{question}</p>
                <p className="text-sm text-[var(--muted)]">{answer}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </main>
  );
}
