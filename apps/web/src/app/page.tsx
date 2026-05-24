import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Vantio AI — Absolute Kernel-Level AI Containment",
  description:
    "Physics over linguistics. Every AI agent action intercepted and evaluated at the kernel boundary before it can affect your systems.",
};

const STATS = [
  { value: "< 1ms", label: "Wave Function Collapse" },
  { value: "Ring-0", label: "eBPF Enforcement Boundary" },
  { value: "Groth16", label: "zk-SNARK Anomaly Records" },
  { value: "SLSA L3", label: "Verified Supply Chain" },
];

const COMPONENTS = [
  {
    num: "01", accent: "text-[--accent]",
    title: "Phantom Engine",
    sub: "Ring-0 eBPF Hypervisor",
    body: "Pure Rust eBPF compiled to bpfel-unknown-none and loaded via Aya. Every agent syscall — execve, openat, connect — intercepted at the kernel boundary before it can affect your filesystem, network, or external state.",
  },
  {
    num: "02", accent: "text-blue-400",
    title: "Oracle zkVM",
    sub: "Policy Evaluation Engine",
    body: "Your governance policy compiled to a RISC Zero zkVM guest program. Synchronous Wave Function Collapse — deterministic policy evaluation completing with microsecond-scale blocking and a cryptographic proof of compliance.",
  },
  {
    num: "03", accent: "text-red-400",
    title: "Anomaly Record",
    sub: "Cryptographic Compliance Ledger",
    body: "A cryptographically sealed, append-only compliance receipt. Groth16 zk-SNARK proof committed to a TrueTime-stamped Spanner ledger or a sovereign local substrate. Immutable by design — zero trust assumptions.",
  },
];

const TIERS = [
  {
    label: "TIER 01", name: "Developer SDK",
    tagline: "Two lines. Any stack.", price: "$0", period: "Free forever",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
    cta: "Start Free", href: "/developers",
    features: ["10,000 events / month", "Node.js + Python SDK", "HMAC-signed telemetry",
      "Oracle UI dashboard", "shield() interceptor", "Community SLA"],
  },
  {
    label: "TIER 02", name: "PRO / SMB", badge: "Most Popular",
    tagline: "Managed proxy. Zero infrastructure.", price: "$499", period: "/month",
    color: "text-blue-400", border: "border-blue-400/40", bg: "bg-blue-400/5",
    cta: "Start 14-Day Trial", href: "/pricing",
    features: ["Transparent HTTPS interception", "5–25ms policy enforcement",
      "30-day Spanner WORM log", "Multi-provider routing", "Stripe self-serve", "24hr email SLA"],
  },
  {
    label: "TIER 03", name: "Enterprise",
    tagline: "Sovereign VPC. CISO-grade control.", price: "Custom", period: "ARR from $50k",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    cta: "Contact Enterprise Sales", href: "/enterprise",
    features: ["Ring-0 eBPF Physical Containment", "Helm / DaemonSet deploy",
      "7-year WORM retention", "SAML 2.0 / Okta", "Dual-auth kill-switches", "Dedicated SLA"],
  },
];

export default function HomePage() {
  return (
    <main>
      {/* Hero */}
      <section className="relative mx-auto max-w-5xl px-6 pb-24 pt-32 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-[--border] bg-[--surface] px-4 py-1.5 text-xs text-[--muted]">
          <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
          SLSA Level 3 Supply Chain · RISC Zero zk-SNARKs · WORM Compliance Ledger
        </div>
        <h1 className="mt-6 text-5xl font-bold leading-tight tracking-tight sm:text-6xl lg:text-7xl">
          Absolute Kernel-Level<br />
          <span className="text-[--accent]">AI Containment.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-[--muted]">
          Physics over linguistics. Every competing AI safety system reads your model's text
          output and calls it a guardrail. Vantio enforces governance at the infrastructure
          layer — before any agent action can affect your systems — and produces a
          cryptographic proof you can hand to a regulator.
        </p>
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <a href="/developers"
            className="rounded-md bg-[--accent] px-8 py-3 text-sm font-semibold text-black transition-colors hover:bg-[--accent-dim]">
            Start Free — npm install
          </a>
          <a href="/architecture"
            className="rounded-md border border-[--border] px-8 py-3 text-sm font-medium text-[--muted] transition-colors hover:border-[--foreground] hover:text-[--foreground]">
            Enterprise Deployment →
          </a>
        </div>
      </section>

      {/* Stats */}
      <section className="border-y border-[--border] bg-[--surface]">
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-px bg-[--border] md:grid-cols-4">
          {STATS.map(({ value, label }) => (
            <div key={label} className="bg-[--surface] px-8 py-8 text-center">
              <p className="text-2xl font-bold">{value}</p>
              <p className="mt-1 text-xs text-[--muted]">{label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Sovereign Protocol */}
      <section className="mx-auto max-w-5xl px-6 py-24">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--accent]">The Sovereign Protocol</p>
        <h2 className="mb-4 text-3xl font-bold">Three components. One atomic operation. Zero trust required.</h2>
        <p className="mb-16 max-w-2xl text-[--muted]">
          The enforcement boundary of the Vantio stack, operating at the deepest layer of your infrastructure.
          Every AI agent action is intercepted and evaluated before it can affect your systems.
        </p>
        <div className="grid gap-6 md:grid-cols-3">
          {COMPONENTS.map(({ num, accent, title, sub, body }) => (
            <div key={num} className="rounded-xl border border-[--border] bg-[--surface] p-6">
              <div className={`mb-4 font-mono text-xs ${accent}`}>{num}</div>
              <h3 className="mb-1 font-semibold">{title}</h3>
              <p className={`mb-3 text-xs font-medium ${accent}`}>{sub}</p>
              <p className="text-sm text-[--muted]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Tier cards */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Choose Your Containment Protocol</p>
          <h2 className="mb-16 text-center text-3xl font-bold">Start free. Scale to sovereign.</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {TIERS.map((t) => (
              <div key={t.name} className={`relative flex flex-col rounded-xl border ${t.border} ${t.bg} p-7`}>
                {t.badge && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-400 px-3 py-0.5 text-xs font-bold text-black">
                    {t.badge}
                  </span>
                )}
                <p className={`mb-1 font-mono text-xs ${t.color}`}>{t.label}</p>
                <h3 className="mb-1 text-lg font-bold">{t.name}</h3>
                <p className="mb-4 text-xs text-[--muted]">{t.tagline}</p>
                <div className="mb-6 flex items-end gap-1">
                  <span className="text-3xl font-bold">{t.price}</span>
                  <span className="mb-0.5 text-xs text-[--muted]">{t.period}</span>
                </div>
                <ul className="mb-8 flex-1 space-y-2">
                  {t.features.map((f) => (
                    <li key={f} className={`flex items-start gap-2 text-xs text-[--muted]`}>
                      <span className={t.color}>→</span> {f}
                    </li>
                  ))}
                </ul>
                <a href={t.href}
                  className={`block rounded-md border ${t.border} px-4 py-2.5 text-center text-sm font-semibold ${t.color} hover:bg-white/5 transition-colors`}>
                  {t.cta}
                </a>
              </div>
            ))}
          </div>
          <p className="mt-10 text-center text-xs text-[--muted]">
            Start with the Developer SDK — zero risk, no credit card. Upgrade to Managed Proxy when you need active
            blocking. Contact Enterprise Sales for sovereign deployment.
          </p>
        </div>
      </section>

      {/* CTA strip */}
      <section className="border-t border-[--border] px-6 py-16 text-center">
        <h2 className="text-2xl font-bold">Ready to enforce your boundary?</h2>
        <p className="mx-auto mt-3 max-w-xl text-sm text-[--muted]">
          Start with the free Developer SDK. 10,000 events/month included. Upgrade when you
          need active blocking or sovereign deployment.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <a href="/developers"
            className="rounded-md bg-[--accent] px-6 py-2.5 text-sm font-semibold text-black hover:bg-[--accent-dim]">
            Explore Developer Tier — Free
          </a>
          <a href="/pricing"
            className="rounded-md border border-blue-400/40 px-6 py-2.5 text-sm font-medium text-blue-400 hover:bg-blue-400/5">
            Explore PRO / SMB Tier — $499/mo
          </a>
          <a href="/enterprise"
            className="rounded-md border border-red-400/30 px-6 py-2.5 text-sm font-medium text-red-400 hover:bg-red-400/5">
            Contact Enterprise Sales
          </a>
        </div>
      </section>
    </main>
  );
}
