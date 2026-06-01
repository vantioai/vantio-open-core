"use client";

import { PRICING_FAQ } from "@/lib/faq";

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
    label: "ENTERPRISE", name: "Enterprise",
    for: "For regulated industries and large teams.",
    price: "Custom", period: "from $50k/year",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    cta: "Talk to Sales", href: "/enterprise",
    features: [
      { text: "Strongest-possible enforcement — agents can't send data without your permission", strong: true },
      { text: "Runs inside your own cloud — your data never leaves your walls" },
      { text: "7-year tamper-proof audit records" },
      { text: "SAML / Okta single sign-on" },
      { text: "Dedicated support + engineering onboarding" },
      { text: "SOC 2, MiFID II, HIPAA, GDPR compliance ready" },
    ],
  },
  {
    label: "Pro", name: "Pro", badge: "Most Popular",
    for: "For teams deploying AI in production.",
    price: "$499", period: "/month",
    color: "text-blue-400", border: "border-blue-400/40", bg: "bg-blue-400/5",
    cta: "Start 14-Day Free Trial", href: "#",
    features: [
      { text: "Block unauthorized AI calls automatically — no code changes", strong: true },
      { text: "Real-time dashboard of every agent action" },
      { text: "Slack alerts the moment something is blocked" },
      { text: "30-day tamper-proof compliance log" },
      { text: "Works with any AI framework or provider" },
      { text: "Email support — 24-hour response" },
    ],
  },
  {
    label: "DEVELOPER", name: "Free",
    for: "For individuals and open-source projects.",
    price: "$0", period: "forever",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
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
];

export default function PricingPage() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-24">
      <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Pricing</p>
      <h1 className="mb-3 text-center text-4xl font-bold">Simple, honest pricing.</h1>
      <p className="mb-16 text-center text-[--muted]">
        Start free. No credit card. Upgrade when you need active blocking or enterprise controls.
      </p>

      <div className="grid gap-6 md:grid-cols-3">
        {TIERS.map((t) => (
          <div key={t.name} className={`relative flex flex-col rounded-xl border ${t.border} ${t.bg} p-8`}>
            {t.badge && (
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-400 px-3 py-0.5 text-xs font-bold text-black">
                {t.badge}
              </span>
            )}
            <p className={`mb-1 text-xs font-semibold uppercase tracking-widest ${t.color}`}>{t.label}</p>
            <h2 className="mb-1 text-2xl font-bold">{t.name}</h2>
            <p className="mb-5 text-sm text-[--muted]">{t.for}</p>
            <div className="mb-6 flex items-end gap-1">
              <span className="text-4xl font-bold">{t.price}</span>
              <span className="mb-1 text-xs text-[--muted]">{t.period}</span>
            </div>

            {t.href === "#" ? (
              <button onClick={startTrial}
                className="mb-8 w-full rounded-md bg-blue-400 py-3 text-sm font-semibold text-black transition-colors hover:bg-blue-300">
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
                <li key={f.text} className="flex items-start gap-2 text-sm">
                  <span className={`mt-0.5 shrink-0 ${t.color}`}>→</span>
                  <span className={f.strong ? "font-medium text-[--foreground]" : "text-[--muted]"}>{f.text}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      {/* FAQ */}
      <div className="mt-20">
        <h2 className="mb-8 text-xl font-bold">Common questions</h2>
        <div className="grid gap-6 md:grid-cols-2">
          {PRICING_FAQ.map(({ question, answer }) => (
            <div key={question} className="rounded-xl border border-[--border] bg-[--surface] p-5">
              <p className="mb-2 font-semibold">{question}</p>
              <p className="text-sm text-[--muted]">{answer}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}
