import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { HOME_FAQ } from "@/lib/faq";

export const metadata: Metadata = buildMetadata({ path: "/" });

const PROBLEMS = [
  { icon: "🚀", title: "Stuck in pilot mode", body: "Your AI agents work great in testing — but putting them in front of real customers and real data feels too risky to ship. So they sit in pilot purgatory instead of driving revenue." },
  { icon: "⚖️", title: "Compliance keeps saying no", body: "Your legal and risk teams can't sign off on software they can't see or control. Without proof of what your AI did, every launch turns into a months-long debate." },
  { icon: "💸", title: "One mistake gets expensive", body: "An agent shares data it shouldn't, calls the wrong tool, or runs up a huge bill — and you find out after the damage is done. Cleanup always costs more than prevention." },
];

const HOW = [
  { n: "01", title: "Set your rules", body: "Tell Vantio what your agents are allowed to do — which tools they can use, which data they can touch, how much they can spend. Simple settings, no code." },
  { n: "02", title: "Your agents enforce them", body: "Vantio syncs your rules to the SDK running alongside your agent. If it tries to step outside the lines, the SDK redacts or blocks it locally — before any data leaves — and your team gets an instant heads-up." },
  { n: "03", title: "Prove it to anyone", body: "Every action is saved to a clean, tamper-proof history you can hand to your boss, an auditor, or a regulator the moment they ask." },
];

const WHY = [
  { title: "Ship faster, not slower", body: "Stop debating whether agents are safe to launch. Vantio gives you the guardrails to put them in production with confidence — this week, not next quarter." },
  { title: "Your secrets stay secret", body: "Vantio never reads your prompts or your AI's answers. It sees what happened, not what was said. Anonymous, opt-out usage stats help us improve the product — never your content." },
  { title: "Nothing to rebuild", body: "No code changes, no new infrastructure, no team to hire. Most customers are live in under an hour, and it works with the tools you already use." },
  { title: "Your agents never slow down", body: "Vantio runs quietly in the background with effectively zero lag. Your agents move at full speed — you just get a safety net underneath them." },
];

const TIERS = [
  { label: "FREE", name: "Developer", headline: "Start seeing what your agents are doing.",
    price: "$0", period: "forever",
    color: "text-[--accent]", border: "border-[--accent]/20", bg: "bg-[--accent]/5", glow: "hover:shadow-[0_0_30px_rgba(0,232,122,0.1)]",
    cta: "Get Started Free", href: "/developers",
    points: ["See every action your agents take","Live dashboard, updated in real time","Works with Node.js & Python","Free forever — no card required"] },
  { label: "PRO", name: "Pro", headline: "Enforce policy right inside your agents.", badge: "Most Popular",
    price: "$499", period: "/month",
    color: "text-blue-400", border: "border-blue-400/30", bg: "bg-blue-400/5", glow: "hover:shadow-[0_0_30px_rgba(59,130,246,0.12)]",
    cta: "Start 14-Day Free Trial", href: "/pricing", primary: true,
    points: ["Redact PII before it ever leaves your app","Spend caps & host allow/block rules","Tamper-proof audit trail of every action","Anonymized benchmarks vs. peers"] },
  { label: "ENTERPRISE", name: "Enterprise", headline: "Kernel-level enforcement for the agents you enroll.",
    price: "Custom", period: "from $50k/yr",
    color: "text-red-400", border: "border-red-400/20", bg: "bg-red-400/5", glow: "hover:shadow-[0_0_30px_rgba(239,68,68,0.08)]",
    cta: "Talk to Sales", href: "/enterprise",
    points: ["Kernel-level (eBPF) enforcement for enrolled workloads","Runs inside your own cloud","7-year WORM audit records","Aligned with SOC 2, HIPAA & MiFID II"] },
];

export default function HomePage() {
  return (
    <main className="overflow-x-hidden">
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="hero-glow dot-grid relative px-6 pb-32 pt-24 text-center">
        {/* Glow orb */}
        <div className="pointer-events-none absolute left-1/2 top-0 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-[--accent]/5 blur-3xl" />

        <div className="relative mx-auto max-w-4xl">
          <div className="mb-6 inline-flex items-center gap-2.5 rounded-full border border-[--border-2] bg-[--surface]/80 px-4 py-1.5 text-xs text-[--muted] backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
            Used by teams deploying AI in regulated industries
          </div>

          <h1 className="mt-4 text-5xl font-bold leading-[1.08] tracking-tight sm:text-6xl lg:text-7xl">
            Go fully autonomous.<br />
            <span className="bg-gradient-to-r from-[--accent] via-emerald-300 to-[--accent] bg-clip-text text-transparent">
              Stay fully compliant.
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-[--muted]">
            Vantio is the governance layer for autonomous AI agents — secure every agent,
            prove compliance to regulators, and accelerate deployment without slowing your
            team down.
          </p>

          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link href="/developers"
              className="group flex items-center gap-2 rounded-xl bg-[--accent] px-7 py-3.5 text-sm font-bold text-black transition-all hover:bg-[--accent-dim] hover:shadow-[0_0_30px_rgba(0,232,122,0.35)]">
              Start Free — No Credit Card
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </Link>
            <Link href="/pricing"
              className="flex items-center gap-2 rounded-xl border border-[--border-2] bg-[--surface] px-7 py-3.5 text-sm font-medium text-[--muted] transition-all hover:border-[--border] hover:text-[--foreground]">
              See Pricing
            </Link>
          </div>

          {/* Terminal preview */}
          <div className="mx-auto mt-16 max-w-lg overflow-hidden rounded-xl border border-[--border] bg-[--surface] shadow-2xl shadow-black/40">
            <div className="flex items-center gap-1.5 border-b border-[--border] bg-[--surface-2] px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-red-500/70" />
              <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
              <span className="h-3 w-3 rounded-full bg-green-500/70" />
              <span className="ml-2 text-xs text-[--muted]">terminal</span>
            </div>
            <div className="p-4 text-left font-mono text-xs leading-relaxed">
              <p className="text-[--muted]">$ <span className="text-[--accent]">vantio run</span> node agent.js</p>
              <p className="mt-2 text-[--muted]"><span className="text-[--accent]">[ ∅ VANTIO ]</span> Policy synced · enforce mode</p>
              <p className="text-[--muted]">  redact pii : email, credit_card <span className="text-green-400">on</span></p>
              <p className="text-[--muted]">  spend cap  : $50.00 / run</p>
              <p className="text-[--muted]">  allow host : <span className="text-blue-400">api.openai.com</span> <span className="text-green-400">allowed</span></p>
              <p className="mt-2 text-[--muted]"><span className="text-yellow-400">⚠</span>  Request to scraper.unknown.tld</p>
              <p className="text-[--muted]">  not on allow-list  action: <span className="text-red-400">BLOCKED_HOST</span></p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Problem ───────────────────────────────────────────────────────────── */}
      <section className="border-y border-[--border] bg-[--surface] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">The Problem</p>
          <h2 className="mb-14 text-center text-3xl font-bold">
            AI agents can do amazing things.<br />Until one does the wrong thing.
          </h2>
          <div className="grid gap-5 md:grid-cols-3">
            {PROBLEMS.map(({ icon, title, body }) => (
              <div key={title}
                className="group rounded-2xl border border-[--border] bg-[--surface-2] p-6 transition-all hover:border-[--border-2] hover:bg-[--surface]">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[--surface] text-xl shadow-inner">
                  {icon}
                </div>
                <h3 className="mb-2 font-semibold text-[--foreground]">{title}</h3>
                <p className="text-sm leading-relaxed text-[--muted]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">How It Works</p>
          <h2 className="mb-16 text-center text-3xl font-bold">Simple to set up. Safe by default.</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {HOW.map(({ n, title, body }) => (
              <div key={n} className="rounded-2xl border border-[--border] bg-[--surface-2] p-7 transition-all hover:border-[--border-2]">
                <div className="mb-4 font-mono text-4xl font-black leading-none text-[--border-2]">{n}</div>
                <div className="mb-4 h-0.5 w-8 rounded-full bg-[--accent]" />
                <h3 className="mb-2 font-semibold">{title}</h3>
                <p className="text-sm leading-relaxed text-[--muted]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why Vantio ────────────────────────────────────────────────────────── */}
      <section className="border-y border-[--border] bg-[--surface] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Why Vantio</p>
          <h2 className="mb-14 text-center text-3xl font-bold">
            Less risk. Less busywork. More autonomy.
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {WHY.map(({ title, body }) => (
              <div key={title}
                className="flex gap-4 rounded-2xl border border-[--border] bg-[--surface-2] p-5 transition-all hover:border-[--border-2]">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[--accent]/15 text-xs text-[--accent] font-bold">✓</div>
                <div>
                  <h3 className="mb-1 font-semibold">{title}</h3>
                  <p className="text-sm leading-relaxed text-[--muted]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tiers ─────────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">Pricing</p>
          <h2 className="mb-4 text-center text-3xl font-bold">Start free. Upgrade when you&apos;re ready.</h2>
          <p className="mb-14 text-center text-sm text-[--muted]">No long-term contracts. Cancel any time.</p>
          <div className="grid gap-5 md:grid-cols-3">
            {TIERS.map((t) => (
              <div key={t.name}
                className={`relative flex flex-col rounded-2xl border ${t.border} ${t.bg} p-7 transition-all ${t.glow}`}>
                {t.badge && (
                  <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-3 py-0.5 text-xs font-bold text-white shadow-lg shadow-blue-500/25">
                    {t.badge}
                  </span>
                )}
                <p className={`mb-1 text-xs font-semibold uppercase tracking-widest ${t.color}`}>{t.label}</p>
                <h3 className="mb-1 text-xl font-bold">{t.name}</h3>
                <p className="mb-5 text-xs text-[--muted]">{t.headline}</p>
                <div className="mb-6 flex items-end gap-1">
                  <span className="text-4xl font-black">{t.price}</span>
                  <span className="mb-1 text-xs text-[--muted]">{t.period}</span>
                </div>
                <ul className="mb-8 flex-1 space-y-2.5">
                  {t.points.map((p) => (
                    <li key={p} className="flex items-start gap-2 text-xs">
                      <span className={`mt-0.5 shrink-0 ${t.color}`}>→</span>
                      <span className="text-[--muted]">{p}</span>
                    </li>
                  ))}
                </ul>
                {t.primary ? (
                  <Link href={t.href}
                    className="block rounded-xl bg-blue-500 py-3 text-center text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-400 hover:shadow-blue-500/30">
                    {t.cta}
                  </Link>
                ) : (
                  <Link href={t.href}
                    className={`block rounded-xl border ${t.border} py-3 text-center text-sm font-semibold ${t.color} transition-all hover:bg-white/5`}>
                    {t.cta}
                  </Link>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <JsonLd data={faqJsonLd(HOME_FAQ)} />
        <div className="mx-auto max-w-3xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[--muted]">FAQ</p>
          <h2 className="mb-12 text-center text-3xl font-bold">Questions, answered.</h2>
          <div className="space-y-4">
            {HOME_FAQ.map(({ question, answer }) => (
              <details key={question}
                className="group rounded-2xl border border-[--border] bg-[--surface-2] p-6 transition-all hover:border-[--border-2]">
                <summary className="flex cursor-pointer list-none items-center justify-between text-base font-semibold text-[--foreground] [&::-webkit-details-marker]:hidden">
                  {question}
                  <span className="ml-4 shrink-0 text-xl text-[--muted] transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-4 text-sm leading-relaxed text-[--muted]">{answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-t border-[--border] bg-[--surface] px-6 py-20 text-center">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-64 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[--accent]/8 blur-3xl" />
        <div className="relative">
          <h2 className="text-3xl font-bold">Your AI agents are running right now.</h2>
          <p className="mx-auto mt-3 max-w-md text-[--muted]">
            Give them guardrails enforced right where they run, and ship with confidence — set up in minutes, free to start.
          </p>
          <Link href="/developers"
            className="mt-8 inline-flex items-center gap-2 rounded-xl bg-[--accent] px-8 py-3.5 text-sm font-bold text-black transition-all hover:bg-[--accent-dim] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)]">
            Get Started Free →
          </Link>
          <p className="mt-4 text-xs text-[--muted]">No credit card · No infrastructure changes · Works with any AI framework</p>
        </div>
      </section>
    </main>
  );
}
