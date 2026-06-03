import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { HOME_FAQ } from "@/lib/faq";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";

export const metadata: Metadata = buildMetadata({ path: "/" });

// Honest credibility strip — verifiable claims only, no fabricated logos.
const TRUST = [
  "Open-source SDK",
  "We never see your prompts or data",
  "SLSA-attested builds",
  "Live in under an hour",
];

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

export default function HomePage() {
  const proWaitlist = isTier2Waitlist();

  return (
    <main className="overflow-x-hidden">
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="hero-glow dot-grid relative px-6 pb-28 pt-24 text-center">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[500px] w-[800px] -translate-x-1/2 rounded-full bg-[var(--accent)]/5 blur-3xl" />

        <div className="relative mx-auto max-w-4xl">
          {/* Honest credibility strip (no fake logos) */}
          <div className="mb-8 flex flex-wrap items-center justify-center gap-x-2.5 gap-y-2 text-xs text-[var(--muted)]">
            {TRUST.map((item, i) => (
              <span key={item} className="flex items-center gap-2.5">
                {i > 0 && <span className="hidden h-1 w-1 rounded-full bg-[var(--border-2)] sm:inline-block" aria-hidden="true" />}
                <span>{item}</span>
              </span>
            ))}
          </div>

          <h1 className="text-5xl font-bold leading-[1.08] tracking-tight sm:text-6xl lg:text-7xl">
            Set your AI agents free.<br />
            <span className="bg-gradient-to-r from-[var(--accent)] via-emerald-300 to-[var(--accent)] bg-clip-text text-transparent">
              Without losing control.
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-[var(--muted)]">
            <span className="font-semibold text-[var(--foreground)]">See</span> everything your autonomous agents do.{" "}
            <span className="font-semibold text-[var(--foreground)]">Stop</span> what they shouldn&apos;t.{" "}
            <span className="font-semibold text-[var(--foreground)]">Prove</span> it to anyone who asks — from your
            first script to your entire enterprise.
          </p>

          <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
            <Link href="/developers"
              className="group flex items-center gap-2 rounded-xl bg-[var(--accent)] px-8 py-3.5 text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_40px_rgba(0,232,122,0.4)]">
              Start free
              <span className="transition-transform group-hover:translate-x-0.5">→</span>
            </Link>
            <a href="#how"
              className="flex items-center gap-2 rounded-xl border border-[var(--border-2)] bg-[var(--surface)] px-6 py-3.5 text-sm font-medium text-[var(--muted)] transition-all hover:border-[var(--border)] hover:text-[var(--foreground)]">
              See how it works
            </a>
          </div>

          {/* Terminal preview */}
          <div className="mx-auto mt-16 max-w-lg overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl shadow-black/40">
            <div className="flex items-center gap-1.5 border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-2.5">
              <span className="h-3 w-3 rounded-full bg-red-500/70" />
              <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
              <span className="h-3 w-3 rounded-full bg-green-500/70" />
              <span className="ml-2 text-xs text-[var(--muted)]">agent.js — vantio</span>
            </div>
            <div className="space-y-1 p-4 text-left font-mono text-xs leading-relaxed">
              <p className="text-[var(--muted)]">$ <span className="text-[var(--accent)]">vantio run</span> node agent.js</p>
              <p className="text-[var(--muted)]"><span className="text-[var(--accent)]">[ ∅ VANTIO ]</span> policy synced · enforce mode</p>
              <p className="text-[var(--muted)]">  redact pii : email, credit_card <span className="text-green-400">on</span></p>
              <p className="text-[var(--muted)]">  spend cap  : $50.00 / run</p>
              <p className="text-[var(--muted)]">  allow host : <span className="text-blue-400">api.openai.com</span> <span className="text-green-400">allowed</span></p>
              <p className="pt-1 text-[var(--muted)]"><span className="text-yellow-400">⚠</span>  request → scraper.unknown.tld</p>
              <p className="text-[var(--muted)]">  not on allow-list · action: <span className="text-red-400">BLOCKED_HOST</span></p>
              <p className="text-[var(--muted)]"><span className="text-[var(--accent)]">✓</span> 1 action blocked · audit log written</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Where do you fit? (persona → tier) ─────────────────────────────────── */}
      <section id="fit" className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Where do you fit?</p>
          <h2 className="mb-4 text-center text-3xl font-bold">One platform. Three ways in.</h2>
          <p className="mx-auto mb-14 max-w-xl text-center text-sm text-[var(--muted)]">
            Start where you are and grow into the rest — the SDK, dashboard, and audit trail
            are the same at every tier.
          </p>

          <div className="grid items-stretch gap-5 md:grid-cols-3">
            {/* Developer → Free */}
            <div className="flex flex-col rounded-2xl border border-[var(--accent)]/25 bg-[var(--accent)]/5 p-7 transition-all hover:border-[var(--accent)]/40 hover:shadow-[0_0_40px_rgba(0,232,122,0.1)]">
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">I&apos;m a developer</p>
              <h3 className="mt-2 text-lg font-bold text-[var(--foreground)]">See what your agents actually do</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                You&apos;re shipping AI agents and want real visibility — every tool call, every host,
                every byte — without touching your code.
              </p>
              <div className="mt-5 flex items-baseline gap-2">
                <span className="rounded-full bg-[var(--accent)]/10 px-2.5 py-0.5 text-xs font-bold text-[var(--accent)]">FREE</span>
                <span className="text-2xl font-black text-[var(--foreground)]">$0</span>
                <span className="text-xs text-[var(--muted)]">forever</span>
              </div>
              <ul className="mb-7 mt-5 flex-1 space-y-2 text-xs text-[var(--muted)]">
                {["Every agent action, live", "Works with Node.js & Python", "No credit card required"].map((p) => (
                  <li key={p} className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-[var(--accent)]">→</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
              <Link href="/developers"
                className="mt-auto block rounded-xl bg-[var(--accent)] py-3 text-center text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_30px_rgba(0,232,122,0.3)]">
                Start free →
              </Link>
            </div>

            {/* Business → Pro (waitlist-aware) */}
            <div className="relative flex flex-col rounded-2xl border border-blue-400/30 bg-blue-400/5 p-7 transition-all hover:border-blue-400/50 hover:shadow-[0_0_40px_rgba(59,130,246,0.12)]">
              <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-3 py-0.5 text-xs font-bold text-white shadow-lg shadow-blue-500/25">
                Most teams
              </span>
              <p className="text-xs font-semibold uppercase tracking-widest text-blue-400">I run a business</p>
              <h3 className="mt-2 text-lg font-bold text-[var(--foreground)]">Put agents in front of customers</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                You&apos;re deploying AI and marketplace agents for real customers and need enforceable
                guardrails — not just dashboards.
              </p>
              <div className="mt-5 flex items-baseline gap-2">
                <span className="rounded-full bg-blue-400/10 px-2.5 py-0.5 text-xs font-bold text-blue-400">PRO</span>
                <span className="text-2xl font-black text-[var(--foreground)]">$499</span>
                <span className="text-xs text-[var(--muted)]">/month</span>
              </div>
              <ul className="mb-7 mt-5 flex-1 space-y-2 text-xs text-[var(--muted)]">
                {["Redact PII before it ever leaves", "Spend caps & host allow/block rules", "Tamper-proof audit trail"].map((p) => (
                  <li key={p} className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-blue-400">→</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
              {proWaitlist ? (
                <div className="mt-auto">
                  <span className="mb-2 inline-flex w-fit items-center gap-1.5 rounded-full border border-blue-400/30 bg-blue-400/10 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-blue-400">
                    <span className="h-1 w-1 rounded-full bg-blue-400" /> Launching soon
                  </span>
                  <WaitlistCta
                    source="home"
                    label="Join the waitlist"
                    buttonClassName="block w-full rounded-xl bg-blue-500 py-3 text-center text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-400 hover:shadow-blue-500/30"
                  />
                </div>
              ) : (
                <Link href="/pricing"
                  className="mt-auto block rounded-xl bg-blue-500 py-3 text-center text-sm font-bold text-white shadow-lg shadow-blue-500/20 transition-all hover:bg-blue-400 hover:shadow-blue-500/30">
                  Start 14-day free trial →
                </Link>
              )}
            </div>

            {/* Enterprise */}
            <div className="flex flex-col rounded-2xl border border-red-400/25 bg-red-400/5 p-7 transition-all hover:border-red-400/40 hover:shadow-[0_0_40px_rgba(239,68,68,0.1)]">
              <p className="text-xs font-semibold uppercase tracking-widest text-red-400">I&apos;m enterprise</p>
              <h3 className="mt-2 text-lg font-bold text-[var(--foreground)]">Autonomous AI at scale, safely</h3>
              <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                You&apos;re running autonomous AI across the org and need to do the impossible —
                provably, inside your own cloud.
              </p>
              <div className="mt-5 flex items-baseline gap-2">
                <span className="rounded-full bg-red-400/10 px-2.5 py-0.5 text-xs font-bold text-red-400">ENTERPRISE</span>
                <span className="text-2xl font-black text-[var(--foreground)]">Custom</span>
                <span className="text-xs text-[var(--muted)]">from $50k/yr</span>
              </div>
              <ul className="mb-7 mt-5 flex-1 space-y-2 text-xs text-[var(--muted)]">
                {["Kernel-level (eBPF) enforcement", "Runs inside your own cloud", "7-year WORM audit records"].map((p) => (
                  <li key={p} className="flex items-start gap-2">
                    <span className="mt-0.5 shrink-0 text-red-400">→</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
              <Link href="/enterprise"
                className="mt-auto block rounded-xl border border-red-400/30 py-3 text-center text-sm font-bold text-red-400 transition-all hover:bg-red-400/10">
                Talk to sales →
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* ── Problem ───────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">The Problem</p>
          <h2 className="mb-14 text-center text-3xl font-bold">
            AI agents can do amazing things.<br />Until one does the wrong thing.
          </h2>
          <div className="grid gap-5 md:grid-cols-3">
            {PROBLEMS.map(({ icon, title, body }) => (
              <div key={title}
                className="group rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-6 transition-all hover:border-[var(--border-2)] hover:bg-[var(--surface)]">
                <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--surface)] text-xl shadow-inner">
                  {icon}
                </div>
                <h3 className="mb-2 font-semibold text-[var(--foreground)]">{title}</h3>
                <p className="text-sm leading-relaxed text-[var(--muted)]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ──────────────────────────────────────────────────────── */}
      <section id="how" className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">How It Works</p>
          <h2 className="mb-16 text-center text-3xl font-bold">Simple to set up. Safe by default.</h2>
          <div className="grid gap-6 md:grid-cols-3">
            {HOW.map(({ n, title, body }) => (
              <div key={n} className="rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-7 transition-all hover:border-[var(--border-2)]">
                <div className="mb-4 font-mono text-4xl font-black leading-none text-[var(--border-2)]">{n}</div>
                <div className="mb-4 h-0.5 w-8 rounded-full bg-[var(--accent)]" />
                <h3 className="mb-2 font-semibold">{title}</h3>
                <p className="text-sm leading-relaxed text-[var(--muted)]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Why Vantio ────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Why Vantio</p>
          <h2 className="mb-14 text-center text-3xl font-bold">
            Less risk. Less busywork. More autonomy.
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            {WHY.map(({ title, body }) => (
              <div key={title}
                className="flex gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-5 transition-all hover:border-[var(--border-2)]">
                <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/15 text-xs font-bold text-[var(--accent)]">✓</div>
                <div>
                  <h3 className="mb-1 font-semibold">{title}</h3>
                  <p className="text-sm leading-relaxed text-[var(--muted)]">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <JsonLd data={faqJsonLd(HOME_FAQ)} />
        <div className="mx-auto max-w-3xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">FAQ</p>
          <h2 className="mb-12 text-center text-3xl font-bold">Questions, answered.</h2>
          <div className="space-y-4">
            {HOME_FAQ.map(({ question, answer }) => (
              <details key={question}
                className="group rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-6 transition-all hover:border-[var(--border-2)]">
                <summary className="flex cursor-pointer list-none items-center justify-between text-base font-semibold text-[var(--foreground)] [&::-webkit-details-marker]:hidden">
                  {question}
                  <span className="ml-4 shrink-0 text-xl text-[var(--muted)] transition-transform group-open:rotate-45">+</span>
                </summary>
                <p className="mt-4 text-sm leading-relaxed text-[var(--muted)]">{answer}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden border-t border-[var(--border)] bg-[var(--surface)] px-6 py-20 text-center">
        <div className="pointer-events-none absolute left-1/2 top-1/2 h-64 w-96 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--accent)]/8 blur-3xl" />
        <div className="relative">
          <h2 className="text-3xl font-bold">Your AI agents are running right now.</h2>
          <p className="mx-auto mt-3 max-w-md text-[var(--muted)]">
            Give them guardrails enforced right where they run, and ship with confidence —
            set up in minutes, free to start.
          </p>
          <Link href="/developers"
            className="mt-8 inline-flex items-center gap-2 rounded-xl bg-[var(--accent)] px-8 py-3.5 text-sm font-bold text-black transition-all hover:bg-[var(--accent-dim)] hover:shadow-[0_0_40px_rgba(0,232,122,0.35)]">
            Start free →
          </Link>
          <p className="mt-4 text-xs text-[var(--muted)]">No credit card · No infrastructure changes · Works with any AI framework</p>
        </div>
      </section>
    </main>
  );
}
