import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { isTier2Waitlist } from "@/lib/tier2";
import { WaitlistCta } from "@/components/waitlist-cta";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = buildMetadata({
  title: "Pro",
  description: "Vantio Pro enforces PII redaction, spend caps, and host blocking inside your own SDK — no ops team, no infrastructure, live in under an hour.",
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
          <span className="font-semibold text-[var(--foreground)]">Vantio Pro</span> pushes a policy you
          control down to the SDK running alongside your agent. PII gets redacted, off-policy hosts get
          blocked, and spend gets capped right where your agent runs — before anything leaves your
          environment. No proxy, no infrastructure to manage, no code to change. You can run it yourself
          in under an hour without a security team or a procurement cycle.
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

      {/* Single ROI callout — governance ships AI faster */}
      <div className="border-t border-[var(--accent)]/15 bg-[var(--surface)] px-6 py-6">
        <div className="mx-auto flex max-w-4xl flex-col items-center gap-1 text-center sm:flex-row sm:justify-center sm:gap-6 sm:text-left">
          <span className="text-5xl font-black leading-none tracking-tight text-[var(--accent)]">12×</span>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">
              more AI projects ship to production with governance in place
            </p>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]/60">
              Databricks 2026 State of AI Agents · vendor telemetry · 20,000+ orgs · directional
            </p>
          </div>
        </div>
      </div>

      {/* What you actually get */}
      <section className="border-t border-[var(--border)] bg-[var(--surface)] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">What You Get</h2>
          <p className="mb-12 text-center text-2xl font-bold">Four things Pro does for you.</p>
          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
            {[
              { icon: "🛡️", title: "PII redaction", body: "Emails, SSNs, and credit card numbers are stripped from requests inside the SDK before they leave your environment. Vantio never sees the original content." },
              { icon: "💰", title: "Spend caps", body: "Set a per-run dollar ceiling. When an agent hits it, the SDK halts further spend locally — a per-process brake on runaway loops and surprise bills." },
              { icon: "🚫", title: "Host & policy blocking", body: "Allow only the hosts you trust and block everything else — any named host, not just known LLM providers. Off-policy calls are stopped client-side and logged." },
              { icon: "📝", title: "Full audit trail", body: "Every decision — observed, allowed, redacted, or blocked — is sealed into a tamper-proof, metadata-only ledger. Export to CSV any time." },
              { icon: "🎛️", title: "Policy editor", body: "Toggle enforcement, choose PII types, and edit host rules from your dashboard. Changes sync to your SDK on the next config pull." },
              { icon: "📊", title: "Peer benchmarks", body: "See how your call volume and block rate compare against anonymized industry peers. No tenant is ever identifiable." },
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
        <h2 className="mb-2 text-2xl font-bold">Two commands, then you&apos;re live.</h2>
        <p className="mb-6 text-[var(--muted)]">
          Start your trial, grab your key, then run these two commands. No env vars, no code changes.
        </p>
        <CodeBlock code={"vantio login <your-key>     # once — saved to ~/.vantio\nvantio run node agent.js"} className="bg-black/40" />
        <p className="mt-5 rounded-xl border border-blue-400/20 bg-blue-400/5 p-4 text-sm text-[var(--muted)]">
          <span className="font-semibold text-[var(--foreground)]">
            Your API key and a copy-paste quickstart are waiting in your{" "}
            <a href="/dashboard" className="text-blue-400 underline">dashboard</a>.
          </span>{" "}
          It prefills your real key into <code className="rounded bg-[var(--surface)] px-1 text-blue-400">vantio login</code>, and agent activity shows up there in real time.
        </p>
        <p className="mt-10 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm text-[var(--muted)]">
          <span className="font-semibold text-[var(--foreground)]">Metadata only.</span> Vantio records
          that an action happened — never the content of your prompts or completions. Enforcement
          and redaction run in your SDK; the cloud stores your policy and the audit trail.
          If our control plane goes down, the SDK <span className="font-semibold text-[var(--foreground)]">fails open</span> —
          your agent keeps running. A Vantio outage will never block you. Anonymous, opt-out
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
