import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, faqJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { HOME_FAQ } from "@/lib/faq";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";
import { ContainmentVisual } from "@/components/containment-visual";
import { DashboardVisual } from "@/components/dashboard-visual";
import { Reveal } from "@/components/reveal";

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

const svg = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const HOW = [
  {
    n: "01",
    title: "Set your rules",
    body: "Tell Vantio what your agents can do — which tools, which data, how much they can spend. Simple settings, no code.",
    icon: (
      <svg {...svg}>
        <line x1="4" y1="7" x2="20" y2="7" />
        <line x1="4" y1="12" x2="20" y2="12" />
        <line x1="4" y1="17" x2="20" y2="17" />
        <circle cx="9" cy="7" r="2.2" fill="currentColor" stroke="none" />
        <circle cx="15" cy="12" r="2.2" fill="currentColor" stroke="none" />
        <circle cx="8" cy="17" r="2.2" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    n: "02",
    title: "Your agents enforce them",
    body: "The SDK runs alongside your agent and redacts or blocks locally — before any data leaves — and pings your team the instant it does.",
    icon: (
      <svg {...svg}>
        <path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
  {
    n: "03",
    title: "Prove it to anyone",
    body: "Every action is written to a clean, tamper-proof history you can hand to your boss, an auditor, or a regulator on demand.",
    icon: (
      <svg {...svg}>
        <path d="M8 4h8a1 1 0 0 1 1 1v15a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1z" />
        <line x1="9.5" y1="9" x2="14.5" y2="9" />
        <line x1="9.5" y1="12.5" x2="14.5" y2="12.5" />
        <line x1="9.5" y1="16" x2="12.5" y2="16" />
      </svg>
    ),
  },
];

const WHY = [
  { title: "Ship faster, not slower", body: "Stop debating whether agents are safe to launch. Vantio gives you the guardrails to put them in production with confidence — this week, not next quarter." },
  { title: "Your secrets stay secret", body: "Vantio never reads your prompts or your AI's answers. It sees what happened, not what was said. Anonymous, opt-out usage stats help us improve the product — never your content." },
  { title: "Nothing to rebuild", body: "No code changes, no new infrastructure, no team to hire. Most customers are live in under an hour, and it works with the tools you already use." },
  { title: "Your agents never slow down", body: "Vantio runs quietly in the background with effectively zero lag. Your agents move at full speed — you just get a safety net underneath them." },
];

// Persona icons (decorative).
const IconDeveloper = (
  <svg {...svg}>
    <polyline points="8 7 3 12 8 17" />
    <polyline points="16 7 21 12 16 17" />
    <line x1="13.5" y1="5" x2="10.5" y2="19" />
  </svg>
);
const IconBusiness = (
  <svg {...svg}>
    <path d="M3 9l1.5-4.5h15L21 9" />
    <path d="M4.5 9.5V19a1 1 0 0 0 1 1h13a1 1 0 0 0 1-1V9.5" />
    <path d="M9.5 20v-5h5v5" />
  </svg>
);
const IconEnterprise = (
  <svg {...svg}>
    <path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z" />
    <line x1="12" y1="8" x2="12" y2="14" />
    <line x1="9" y1="11" x2="15" y2="11" />
  </svg>
);

export default function HomePage() {
  const proWaitlist = isTier2Waitlist();

  return (
    <main className="overflow-x-hidden">
      {/* ── Hero ──────────────────────────────────────────────────────────────── */}
      <section className="hero-glow dot-grid relative px-6 pb-28 pt-24">
        <div className="pointer-events-none absolute left-1/2 top-0 h-[500px] w-[820px] -translate-x-1/2 rounded-full bg-[var(--accent)]/5 blur-3xl" />

        <div className="relative mx-auto grid max-w-6xl items-center gap-14 lg:grid-cols-2">
          {/* Copy */}
          <div className="text-center lg:text-left">
            {/* Honest credibility strip */}
            <div className="mb-7 flex flex-wrap items-center justify-center gap-x-2.5 gap-y-2 text-xs text-[var(--muted)] lg:justify-start">
              {TRUST.map((item, i) => (
                <span key={item} className="flex items-center gap-2.5">
                  {i > 0 && <span className="hidden h-1 w-1 rounded-full bg-[var(--border-2)] sm:inline-block" aria-hidden="true" />}
                  <span>{item}</span>
                </span>
              ))}
            </div>

            {/* Kicker */}
            <p className="mb-5 text-sm font-medium text-[var(--muted)]">
              Monitoring tells you an agent went rogue.{" "}
              <span className="font-semibold text-[var(--foreground)]">Vantio makes sure it can&apos;t.</span>
            </p>

            <h1 className="text-5xl font-bold leading-[1.08] tracking-tight sm:text-6xl">
              Set your AI agents free.<br />
              <span className="bg-gradient-to-r from-[var(--accent)] via-emerald-300 to-[var(--accent)] bg-clip-text text-transparent">
                Without losing control.
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-[var(--muted)] lg:mx-0">
              <span className="font-semibold text-[var(--foreground)]">See</span> everything your autonomous agents do.{" "}
              <span className="font-semibold text-[var(--foreground)]">Stop</span> what they shouldn&apos;t.{" "}
              <span className="font-semibold text-[var(--foreground)]">Prove</span> it to anyone who asks — from your
              first script to your entire enterprise.
            </p>

            <div className="mt-10 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start">
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
          </div>

          {/* Living telemetry dashboard — the hero focal piece */}
          <div className="relative">
            <DashboardVisual />
          </div>
        </div>
      </section>

      {/* ── Manifesto: Watching isn't governing ───────────────────────────────── */}
      <section className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <div className="grid items-center gap-14 lg:grid-cols-2">
            <Reveal>
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">Watching isn&apos;t governing</p>
              <h2 className="mt-3 text-3xl font-bold leading-tight sm:text-4xl">
                Everyone else watches your agents.{" "}
                <span className="text-[var(--accent)]">We contain them.</span>
              </h2>
              <div className="mt-6 space-y-4 text-sm leading-relaxed text-[var(--muted)]">
                <p>
                  Monitoring tools light up after an agent leaks data, calls the wrong tool, or burns
                  your budget — a post-mortem, not protection. That&apos;s why agents stay trapped in
                  pilots: nobody can actually promise control.
                </p>
                <p>
                  Vantio is built on one belief: there&apos;s only one right way to govern an autonomous
                  agent — enforce it where it runs, stop it before anything leaves, and never read its
                  data to do it.
                </p>
                <p className="text-[var(--foreground)]">
                  That&apos;s the difference between hoping your agents behave and deploying them at scale.
                </p>
              </div>
              <p className="mt-6 border-l-2 border-[var(--accent)]/50 pl-4 text-sm font-medium text-[var(--foreground)]">
                This is the control layer that finally takes agents out of pilot purgatory.
              </p>
            </Reveal>

            <Reveal delayMs={120}>
              <ContainmentVisual />
              <p className="mx-auto mt-5 max-w-sm text-center text-xs leading-relaxed text-[var(--muted)]">
                Allowed traffic flows out; the rogue request is severed at the boundary.
                Observe stops at the dashboard — <span className="text-[var(--foreground)]">Vantio stops it here.</span>
              </p>
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Problem ───────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">The Problem</p>
            <h2 className="mb-14 text-center text-3xl font-bold">
              AI agents can do amazing things.<br />Until one does the wrong thing.
            </h2>
          </Reveal>
          <div className="grid gap-5 md:grid-cols-3">
            {PROBLEMS.map(({ icon, title, body }, i) => (
              <Reveal key={title} delayMs={i * 90} className="h-full">
                <div className="lift h-full rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-6 hover:border-[var(--border-2)] hover:bg-[var(--surface)]">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--surface)] text-xl shadow-inner">
                    {icon}
                  </div>
                  <h3 className="mb-2 font-semibold text-[var(--foreground)]">{title}</h3>
                  <p className="text-sm leading-relaxed text-[var(--muted)]">{body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works (connected flow) ─────────────────────────────────────── */}
      <section id="how" className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">How It Works</p>
            <h2 className="mb-16 text-center text-3xl font-bold">Simple to set up. Safe by default.</h2>
          </Reveal>

          <div className="relative">
            {/* animated connectors (decorative): horizontal on desktop, vertical on mobile */}
            <div className="flow-connector absolute left-[16%] right-[16%] top-7 hidden h-px md:block" aria-hidden="true" />
            <div className="flow-connector-v absolute bottom-12 left-7 top-7 w-px md:hidden" aria-hidden="true" />

            <div className="grid gap-10 md:grid-cols-3">
              {HOW.map((s, i) => (
                <Reveal key={s.n} delayMs={i * 110}>
                  <div className="relative flex gap-5 md:flex-col md:items-center md:text-center">
                    <div className="relative z-10 flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-[var(--border-2)] bg-[var(--surface-2)] text-[var(--accent)] shadow-lg shadow-black/20">
                      {s.icon}
                    </div>
                    <div className="md:mt-5">
                      <div className="font-mono text-xs font-bold tracking-widest text-[var(--accent)]">{s.n}</div>
                      <h3 className="mt-1 font-semibold text-[var(--foreground)]">{s.title}</h3>
                      <p className="mt-1.5 text-sm leading-relaxed text-[var(--muted)]">{s.body}</p>
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── See it in action (relocated, polished terminal) ───────────────────── */}
      <section id="see-it" className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="grid items-center gap-12 lg:grid-cols-2">
            <Reveal>
              <p className="text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">See it in action</p>
              <h2 className="mt-3 text-3xl font-bold leading-tight">
                One command. Enforcement and a receipt.
              </h2>
              <p className="mt-4 text-sm leading-relaxed text-[var(--muted)]">
                Wrap your agent with the Vantio SDK or CLI. Policy syncs locally, PII is redacted before
                it leaves, off-policy hosts are severed at the edge — and every decision lands in a
                tamper-proof log. No proxy, no prompt content, no slowdown.
              </p>
              <Link href="/developers"
                className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-[var(--accent)] transition-colors hover:text-[var(--accent-dim)]">
                Read the developer quickstart →
              </Link>
            </Reveal>

            <Reveal delayMs={120}>
              <div className="overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--surface)] shadow-2xl shadow-black/40">
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
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Where do you fit? (persona → tier) ─────────────────────────────────── */}
      <section id="fit" className="border-y border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <div className="mx-auto max-w-6xl">
          <Reveal>
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Where do you fit?</p>
            <h2 className="mb-4 text-center text-3xl font-bold">One platform. Three ways in.</h2>
            <p className="mx-auto mb-14 max-w-xl text-center text-sm text-[var(--muted)]">
              Start where you are and grow into the rest — the SDK, dashboard, and audit trail
              are the same at every tier.
            </p>
          </Reveal>

          <div className="grid items-stretch gap-5 md:grid-cols-3">
            {/* Developer → Free */}
            <Reveal className="h-full">
              <div className="border-gradient-green lift flex h-full flex-col rounded-2xl p-7 hover:shadow-[0_0_40px_rgba(0,232,122,0.12)]">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)]/10 text-[var(--accent)]">{IconDeveloper}</div>
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
            </Reveal>

            {/* Business → Pro (waitlist-aware) */}
            <Reveal className="h-full" delayMs={90}>
              <div className="border-gradient-blue lift relative flex h-full flex-col rounded-2xl p-7 hover:shadow-[0_0_40px_rgba(59,130,246,0.14)]">
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-3 py-0.5 text-xs font-bold text-white shadow-lg shadow-blue-500/25">
                  Most popular
                </span>
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-blue-400/10 text-blue-400">{IconBusiness}</div>
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
            </Reveal>

            {/* Enterprise */}
            <Reveal className="h-full" delayMs={180}>
              <div className="border-gradient-red lift flex h-full flex-col rounded-2xl p-7 hover:shadow-[0_0_40px_rgba(239,68,68,0.12)]">
                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-red-400/10 text-red-400">{IconEnterprise}</div>
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
            </Reveal>
          </div>
        </div>
      </section>

      {/* ── Why Vantio ────────────────────────────────────────────────────────── */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <Reveal>
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Why Vantio</p>
            <h2 className="mb-14 text-center text-3xl font-bold">
              Less risk. Less busywork. More autonomy.
            </h2>
          </Reveal>
          <div className="grid gap-4 md:grid-cols-2">
            {WHY.map(({ title, body }, i) => (
              <Reveal key={title} delayMs={i * 80} className="h-full">
                <div className="lift flex h-full gap-4 rounded-2xl border border-[var(--border)] bg-[var(--surface-2)] p-5 hover:border-[var(--border-2)]">
                  <div className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/15 text-xs font-bold text-[var(--accent)]">✓</div>
                  <div>
                    <h3 className="mb-1 font-semibold">{title}</h3>
                    <p className="text-sm leading-relaxed text-[var(--muted)]">{body}</p>
                  </div>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* ── FAQ ───────────────────────────────────────────────────────────────── */}
      <section className="border-t border-[var(--border)] bg-[var(--surface)] px-6 py-24">
        <JsonLd data={faqJsonLd(HOME_FAQ)} />
        <div className="mx-auto max-w-3xl">
          <Reveal>
            <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">FAQ</p>
            <h2 className="mb-12 text-center text-3xl font-bold">Questions, answered.</h2>
          </Reveal>
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
