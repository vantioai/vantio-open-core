import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Vantio AI — Know What Your AI Agents Are Doing",
  description:
    "AI agents make decisions and take actions you can't see. Vantio watches every move, stops unauthorized behavior instantly, and creates a tamper-proof record you can hand to an auditor.",
};

const PROBLEMS = [
  { icon: "📤", title: "Data leaving without permission", body: "Your AI agent calls an API, processes a document, then makes an outbound request. Did sensitive data just leave your network? Without Vantio, you have no way to know." },
  { icon: "📋", title: "No audit trail for compliance", body: "Your compliance team asks: \"What did your AI agents do last quarter?\" Without a governance layer, the honest answer is \"we're not sure.\" That's not an answer regulators accept." },
  { icon: "🔓", title: "Agents acting outside their scope", body: "AI agents can spawn subprocesses, open files, make network calls. Any of these could happen outside the boundaries you intended — and you'd only find out after the damage was done." },
];

const HOW = [
  { step: "01", title: "See everything", body: "Vantio watches every action your AI agents take — network calls, file access, subprocess spawning — and logs them to a tamper-proof ledger in real time." },
  { step: "02", title: "Stop what shouldn't happen", body: "Set the boundaries. When an agent tries to cross them, Vantio blocks the action instantly — before a single byte of unauthorized data leaves your environment." },
  { step: "03", title: "Prove it to anyone", body: "Every decision Vantio makes comes with a cryptographic record. Hand it to an auditor, a regulator, or your board. It's independently verifiable — no one has to take your word for it." },
];

const WHY = [
  { title: "We never read your prompts", body: "Vantio works at the operating system level, not the application layer. We see that a request was made — not what was in it. Your sensitive AI inputs stay yours." },
  { title: "Zero code changes required", body: "Run vantio run node agent.js instead of node agent.js. That's the entire integration. Your codebase doesn't change." },
  { title: "Invisible to your agents", body: "Vantio adds under 1 millisecond of overhead. Your agents run at full speed. The governance layer is invisible until something needs to be stopped." },
  { title: "Works with every AI framework", body: "LangChain, AutoGen, CrewAI, OpenAI, Anthropic, Bedrock. If your agent makes network calls, Vantio can watch it." },
];

const TIERS = [
  {
    label: "FREE", name: "Developer",
    headline: "Start seeing what your agents are doing.",
    price: "$0", period: "forever",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
    cta: "Get Started Free", href: "/developers",
    points: ["10,000 agent events/month", "Real-time activity dashboard", "Node.js and Python", "No credit card required"],
  },
  {
    label: "PRO", name: "SMB", badge: "Most Popular",
    headline: "Block unauthorized behavior automatically.",
    price: "$499", period: "/month",
    color: "text-blue-400", border: "border-blue-400/40", bg: "bg-blue-400/5",
    cta: "Start 14-Day Free Trial", href: "/pricing", primary: true,
    points: ["Active blocking — not just logging", "30-day tamper-proof compliance log", "Slack alerts on violations", "No servers to manage"],
  },
  {
    label: "ENTERPRISE", name: "Enterprise",
    headline: "OS-level enforcement. Your agents literally cannot exfiltrate data.",
    price: "Custom", period: "from $50k/yr",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    cta: "Talk to Sales", href: "/enterprise",
    points: ["Kernel-level enforcement (nothing bypasses it)", "Deploys in your own Kubernetes cluster", "7-year tamper-proof audit records", "SOC 2, MiFID II, HIPAA ready"],
  },
];

export default function HomePage() {
  return (
    <main>
      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 pb-20 pt-28 text-center">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[--border] bg-[--surface] px-4 py-1.5 text-xs text-[--muted]">
          <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
          Used by teams deploying AI in regulated industries
        </div>
        <h1 className="mt-4 text-5xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
          Know what your AI agents<br />
          <span className="text-[--accent]">are actually doing.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-xl text-[--muted]">
          AI agents make decisions and take actions you can&apos;t see. Vantio watches every move,
          stops unauthorized behavior instantly, and creates a tamper-proof record you can hand
          to an auditor.
        </p>
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <a href="/developers"
            className="rounded-md bg-[--accent] px-8 py-3.5 text-sm font-semibold text-black transition-colors hover:bg-[--accent-dim]">
            Start Free — No Credit Card
          </a>
          <a href="/pricing"
            className="rounded-md border border-[--border] px-8 py-3.5 text-sm font-medium text-[--muted] transition-colors hover:border-[--foreground] hover:text-[--foreground]">
            See Pricing →
          </a>
        </div>
      </section>

      {/* Problem */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">The Problem</h2>
          <p className="mb-12 text-center text-2xl font-bold">
            AI agents are powerful. They&apos;re also unsupervised.
          </p>
          <div className="grid gap-6 md:grid-cols-3">
            {PROBLEMS.map(({ icon, title, body }) => (
              <div key={title} className="rounded-xl border border-[--border] bg-[--background] p-6">
                <div className="mb-4 text-3xl">{icon}</div>
                <h3 className="mb-2 font-semibold">{title}</h3>
                <p className="text-sm text-[--muted]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">How It Works</h2>
        <p className="mb-14 text-center text-2xl font-bold">Three things. In that order.</p>
        <div className="grid gap-8 md:grid-cols-3">
          {HOW.map(({ step, title, body }) => (
            <div key={step} className="relative">
              <div className="mb-4 font-mono text-4xl font-bold text-[--accent]/30">{step}</div>
              <h3 className="mb-2 text-lg font-bold">{title}</h3>
              <p className="text-sm text-[--muted]">{body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Why different */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Why Vantio</h2>
          <p className="mb-12 text-center text-2xl font-bold">Built for teams that can&apos;t afford to guess.</p>
          <div className="grid gap-6 md:grid-cols-2">
            {WHY.map(({ title, body }) => (
              <div key={title} className="flex gap-4 rounded-xl border border-[--border] bg-[--background] p-6">
                <span className="mt-0.5 shrink-0 text-[--accent]">✓</span>
                <div>
                  <h3 className="mb-1 font-semibold">{title}</h3>
                  <p className="text-sm text-[--muted]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Tiers */}
      <section className="mx-auto max-w-6xl px-6 py-20">
        <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Pricing</h2>
        <p className="mb-14 text-center text-2xl font-bold">Start free. Upgrade when you&apos;re ready.</p>
        <div className="grid gap-6 md:grid-cols-3">
          {TIERS.map((t) => (
            <div key={t.name} className={`relative flex flex-col rounded-xl border ${t.border} ${t.bg} p-8`}>
              {t.badge && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-400 px-3 py-0.5 text-xs font-bold text-black">
                  {t.badge}
                </span>
              )}
              <span className={`mb-2 text-xs font-semibold uppercase tracking-widest ${t.color}`}>{t.label}</span>
              <h3 className="mb-1 text-xl font-bold">{t.name}</h3>
              <p className="mb-4 text-sm text-[--muted]">{t.headline}</p>
              <div className="mb-6 flex items-end gap-1">
                <span className="text-3xl font-bold">{t.price}</span>
                <span className="mb-0.5 text-xs text-[--muted]">{t.period}</span>
              </div>
              <ul className="mb-8 flex-1 space-y-2">
                {t.points.map((p) => (
                  <li key={p} className="flex items-start gap-2 text-sm text-[--muted]">
                    <span className={`shrink-0 ${t.color}`}>→</span> {p}
                  </li>
                ))}
              </ul>
              {t.primary ? (
                <a href={t.href}
                  className="block rounded-md bg-blue-400 py-3 text-center text-sm font-semibold text-black transition-colors hover:bg-blue-300">
                  {t.cta}
                </a>
              ) : (
                <a href={t.href}
                  className={`block rounded-md border ${t.border} py-3 text-center text-sm font-semibold ${t.color} transition-colors hover:bg-white/5`}>
                  {t.cta}
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-16 text-center">
        <h2 className="text-2xl font-bold">Your AI agents are running right now.</h2>
        <p className="mx-auto mt-3 max-w-lg text-[--muted]">
          Do you know what they&apos;re doing? Start watching in under 60 seconds — for free.
        </p>
        <a href="/developers"
          className="mt-8 inline-block rounded-md bg-[--accent] px-8 py-3.5 text-sm font-semibold text-black transition-colors hover:bg-[--accent-dim]">
          Get Started Free →
        </a>
        <p className="mt-4 text-xs text-[--muted]">
          No credit card. No infrastructure changes. Works with any AI framework.
        </p>
      </section>
    </main>
  );
}
