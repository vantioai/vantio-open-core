import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";

export const metadata: Metadata = buildMetadata({
  title: "Pro",
  description: "Put your AI agents in production with confidence. Vantio Pro automatically stops risky actions, alerts your team, and keeps an audit-ready record — live in minutes, no ops team needed.",
  path: "/pro",
});

export default function ProPage() {
  return (
    <main>
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Pro", path: "/pro" }])} />
      <section className="mx-auto max-w-4xl px-6 pb-16 pt-24 text-center">
        <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-400/30 bg-blue-400/5 px-4 py-1.5 text-xs font-semibold text-blue-400">
          Tier 02 — Pro · $499/month
        </span>
        {isTier2Waitlist() && (
          <span className="mb-4 ml-2 inline-flex items-center gap-2 rounded-full border border-blue-400/30 bg-blue-400/10 px-4 py-1.5 text-xs font-semibold text-blue-400">
            Launching soon
          </span>
        )}
        <h1 className="mb-4 text-4xl font-bold sm:text-5xl">
          Let your agents run free.<br />
          <span className="text-blue-400">You stay in control.</span>
        </h1>
        <p className="mx-auto mb-10 max-w-2xl text-lg text-[var(--muted)]">
          Vantio Pro syncs a policy you control down to the SDK running with your agent. It
          redacts PII, blocks off-policy hosts, and caps spend right where your agent runs —
          before anything leaves your environment. No proxy, no servers to manage, no code to
          change.
        </p>
        <div className="flex flex-wrap items-start justify-center gap-3">
          {isTier2Waitlist() ? (
            <WaitlistCta
              source="pro"
              wrapperClassName="w-full max-w-xs sm:w-auto"
              buttonClassName="w-full rounded-md bg-blue-400 px-6 py-3 text-sm font-semibold text-black hover:bg-blue-300"
            />
          ) : (
            <a href="/pricing"
              className="rounded-md bg-blue-400 px-6 py-3 text-sm font-semibold text-black hover:bg-blue-300">
              Start 14-Day Free Trial
            </a>
          )}
          <a href="/dashboard"
            className="rounded-md border border-blue-400/30 px-6 py-3 text-sm font-medium text-blue-400 hover:bg-blue-400/5">
            View Demo Dashboard
          </a>
        </div>
      </section>

      {/* What you actually get */}
      <section className="border-t border-[var(--border)] bg-[var(--surface)] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">What You Get</h2>
          <p className="mb-12 text-center text-2xl font-bold">Four pillars of SDK-side enforcement.</p>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: "🛡️", title: "PII redaction", body: "Emails, SSNs, credit cards and more are stripped from requests by the SDK before they ever leave your environment. Vantio never sees the original content." },
              { icon: "💰", title: "Spend caps", body: "Set a per-run dollar ceiling. As an agent crosses it, the SDK halts further spend locally — a best-effort, per-process brake on runaway loops and surprise bills." },
              { icon: "🚫", title: "Host & policy blocking", body: "Allow only the hosts you trust and block the rest — any named host, not just known LLM providers. Off-policy calls are stopped client-side and logged as BLOCKED_HOST." },
              { icon: "📝", title: "Full audit trail", body: "Every decision — observed, allowed, redacted, or blocked — is sealed into a tamper-proof, metadata-only ledger. Export to CSV anytime." },
              { icon: "🎛️", title: "Policy editor", body: "Toggle enforcement, choose PII types, edit host rules and limits from your dashboard. Changes sync to your SDK on its next config pull." },
              { icon: "📊", title: "Peer benchmarks", body: "Compare your call volume and block rate against anonymized industry peers. No tenant is ever identifiable." },
            ].map(({ icon, title, body }) => (
              <div key={title} className="rounded-xl border border-[var(--border)] bg-[var(--background)] p-5">
                <div className="mb-3 text-2xl">{icon}</div>
                <h3 className="mb-1 font-semibold">{title}</h3>
                <p className="text-sm text-[var(--muted)]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Setup */}
      <section className="mx-auto max-w-4xl px-6 py-20">
        <h2 className="mb-2 text-2xl font-bold">Running in under 60 seconds.</h2>
        <p className="mb-10 text-[var(--muted)]">Seriously. Here&apos;s the entire integration.</p>
        <div className="space-y-6">
          {[
            { n: "1", title: "Start your trial", body: "Click the button, enter your card. No charge for 14 days. Your account and API key are created instantly." },
            { n: "2", title: "Set two environment variables", body: "VANTIO_API_KEY=your-key-here\nVANTIO_INGEST_URL=https://vantio.ai\n\nThat's the entire configuration." },
            { n: "3", title: "Run your agent through Vantio", body: "vantio run node agent.js\n\nOr: vantio run python agent.py\n\nYour code doesn't change. The CLI handles everything." },
            { n: "4", title: "Watch the dashboard", body: "Open /dashboard. Every AI call your agent makes shows up in real time — what it called, when, and whether it was allowed." },
          ].map(({ n, title, body }) => (
            <div key={n} className="flex gap-6 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
              <span className="mt-0.5 shrink-0 text-2xl font-bold text-blue-400">{n}</span>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-1 whitespace-pre-line text-sm text-[var(--muted)]">{body}</p>
              </div>
            </div>
          ))}
        </div>
        <p className="mt-10 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--muted)]">
          <span className="font-semibold text-[var(--foreground)]">Metadata only.</span> Vantio records
          that an action happened — never the content of your prompts or completions. Enforcement
          and redaction run in your SDK; the cloud just stores your policy and the audit trail.
          If our control plane is ever unreachable, the SDK <span className="font-semibold text-[var(--foreground)]">fails open</span> —
          your agent keeps running and is never blocked by a Vantio outage. Anonymous, opt-out
          usage telemetry helps us improve the product — never your data.
        </p>
        <p className="mt-6 text-sm text-[var(--muted)]">
          Need kernel-level enforcement for regulated workloads?{" "}
          <a href="/enterprise" className="text-red-400 underline">See Enterprise →</a>
        </p>
      </section>
    </main>
  );
}
