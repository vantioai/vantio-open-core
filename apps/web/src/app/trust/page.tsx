import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Trust & Compliance",
  description: "How Vantio protects your data, meets compliance requirements, and proves it.",
  path: "/trust",
});

export default function TrustPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Trust & Compliance", path: "/trust" }])} />
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--accent)]/30 bg-[var(--accent)]/5 px-3 py-1 text-xs font-semibold text-[var(--accent)]">Tier 01</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-400/30 bg-blue-400/5 px-3 py-1 text-xs font-semibold text-blue-400">Tier 02</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1 text-xs font-semibold text-red-400">Tier 03</span>
      </div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Trust Center</p>
      <h1 className="mb-4 text-4xl font-bold">We take your trust seriously.</h1>
      <p className="mb-16 text-[var(--muted)]">
        Vantio is built for regulated industries. Here&apos;s exactly how we protect your data
        and meet the compliance requirements your team cares about.
      </p>

      {/* Key assurances */}
      <div className="mb-16 grid gap-5 sm:grid-cols-2">
        {[
          { icon: "🚫", title: "We never read your prompts", body: "Vantio never sees the content of your AI conversations. We record that something happened — not what was said. Your sensitive data stays yours." },
          { icon: "🔒", title: "Your data never leaves your cloud (Enterprise)", body: "Enterprise runs entirely inside your own cloud, and your records stay in your own database — never ours." },
          { icon: "📋", title: "Tamper-proof audit records", body: "Every Vantio decision is sealed into a history that can't be edited or deleted — not even by us. It's there when an auditor asks." },
          { icon: "🔑", title: "We collect as little as possible", body: "We record what happened — which action, how much data, the outcome — never the actual content of your AI's inputs or outputs." },
        ].map(({ icon, title, body }) => (
          <div key={title} className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5">
            <div className="mb-3 text-2xl">{icon}</div>
            <h3 className="mb-1 font-semibold">{title}</h3>
            <p className="text-sm text-[var(--muted)]">{body}</p>
          </div>
        ))}
      </div>

      {/* Data & telemetry transparency */}
      <div className="mb-16 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6">
        <h2 className="mb-2 text-lg font-semibold">Anonymous usage analytics</h2>
        <p className="text-sm text-[var(--muted)]">
          Across every tier, Vantio collects only anonymous, opt-out usage analytics — an anonymous
          install ID, SDK/CLI version, runtime, OS, and aggregate call/redaction/block counts — to
          improve the product. No prompt or completion content is ever stored, telemetry carries no
          API key, email, or IP address, and cross-tenant benchmarks contain no tenant identifiers.
          Opt out any time with{" "}
          <code className="rounded bg-[var(--surface-2)] px-1">VANTIO_TELEMETRY_DISABLED=1</code> or{" "}
          <code className="rounded bg-[var(--surface-2)] px-1">DO_NOT_TRACK=1</code>.
        </p>
      </div>

      {/* Compliance */}
      <h2 className="mb-4 text-xl font-bold">Compliance signals</h2>
      <p className="mb-6 text-sm text-[var(--muted)]">
        Vantio AI, Inc. is a registered Delaware C-Corporation structured to meet the procurement and vendor risk
        requirements of Fortune 500 institutions. The items below describe how Vantio&apos;s architecture is
        designed and aligned — they are engineering and readiness signals, not a claim of completed
        third-party certification.
      </p>
      <div className="mb-16 grid gap-3 sm:grid-cols-2">
        {[
          ["SOC 2 Type II", "Audit-ready architecture"],
          ["SLSA Level 3", "Build provenance attested (Sigstore/Rekor)"],
          ["ISO 27001 / NIST CSF", "Framework alignment"],
          ["SEC Cybersecurity", "Disclosure rule compliance"],
          ["MiFID II", "TrueTime timestamps for financial audit trails"],
          ["HIPAA", "No PHI stored; infrastructure-layer enforcement"],
          ["GDPR Article 30", "Records of processing activities by design"],
          ["Delaware C-Corp", "SEC & EDGAR-addressable legal entity"],
        ].map(([standard, desc]) => (
          <div key={standard} className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-4 py-3">
            <span className="mt-0.5 text-[var(--accent)]">✓</span>
            <div>
              <p className="text-sm font-semibold">{standard}</p>
              <p className="text-xs text-[var(--muted)]">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Contact */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-6 text-center">
        <h3 className="mb-2 font-semibold">Security questions?</h3>
        <p className="mb-4 text-sm text-[var(--muted)]">Contact our security team directly.</p>
        <a href="mailto:security@vantio.ai"
          className="text-sm font-medium text-[var(--accent)] underline underline-offset-4 hover:text-[var(--accent-dim)]">
          security@vantio.ai
        </a>
      </div>
    </main>
  );
}
