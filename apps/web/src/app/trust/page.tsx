import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trust & Compliance — Vantio AI",
  description: "How Vantio protects your data, meets compliance requirements, and proves it.",
};

export default function TrustPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-24">
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[--accent]/30 bg-[--accent]/5 px-3 py-1 text-xs font-semibold text-[--accent]">Tier 01</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-400/30 bg-blue-400/5 px-3 py-1 text-xs font-semibold text-blue-400">Tier 02</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1 text-xs font-semibold text-red-400">Tier 03</span>
      </div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Trust Center</p>
      <h1 className="mb-4 text-4xl font-bold">We take your trust seriously.</h1>
      <p className="mb-16 text-[--muted]">
        Vantio is built for regulated industries. Here&apos;s exactly how we protect your data
        and meet the compliance requirements your team cares about.
      </p>

      {/* Key assurances */}
      <div className="mb-16 grid gap-5 sm:grid-cols-2">
        {[
          { icon: "🚫", title: "We never read your prompts", body: "Vantio works at the OS and network layer. We record that an AI call was made — not what was in it. Your sensitive data stays yours." },
          { icon: "🔒", title: "Your data never leaves your VPC (Enterprise)", body: "Enterprise deployments run entirely inside your own Kubernetes cluster. Anomaly records are stored in your own Spanner instance." },
          { icon: "📋", title: "Tamper-proof audit records", body: "Every Vantio decision is signed and stored in an append-only ledger. Records cannot be modified or deleted — even by Vantio." },
          { icon: "🔑", title: "Minimal data collection", body: "We collect what happened (which endpoint, how many bytes, the outcome) — never the content of AI inputs or outputs." },
        ].map(({ icon, title, body }) => (
          <div key={title} className="rounded-xl border border-[--border] bg-[--surface] p-5">
            <div className="mb-3 text-2xl">{icon}</div>
            <h3 className="mb-1 font-semibold">{title}</h3>
            <p className="text-sm text-[--muted]">{body}</p>
          </div>
        ))}
      </div>

      {/* Compliance */}
      <h2 className="mb-4 text-xl font-bold">Compliance signals</h2>
      <p className="mb-6 text-sm text-[--muted]">
        Vantio AI, Inc. is a registered Delaware C-Corporation structured to meet the procurement and vendor risk
        requirements of Fortune 500 institutions.
      </p>
      <div className="mb-16 grid gap-3 sm:grid-cols-2">
        {[
          ["SOC 2 Type II", "Audit-ready architecture"],
          ["SLSA Level 3", "Verified supply chain — every release signed"],
          ["ISO 27001 / NIST CSF", "Framework alignment"],
          ["SEC Cybersecurity", "Disclosure rule compliance"],
          ["MiFID II", "TrueTime timestamps for financial audit trails"],
          ["HIPAA", "No PHI stored; infrastructure-layer enforcement"],
          ["GDPR Article 30", "Records of processing activities by design"],
          ["Delaware C-Corp", "SEC & EDGAR-addressable legal entity"],
        ].map(([standard, desc]) => (
          <div key={standard} className="flex items-start gap-3 rounded-lg border border-[--border] bg-[--surface] px-4 py-3">
            <span className="mt-0.5 text-[--accent]">✓</span>
            <div>
              <p className="text-sm font-semibold">{standard}</p>
              <p className="text-xs text-[--muted]">{desc}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Contact */}
      <div className="rounded-xl border border-[--border] bg-[--surface] p-6 text-center">
        <h3 className="mb-2 font-semibold">Security questions?</h3>
        <p className="mb-4 text-sm text-[--muted]">Contact our security team directly.</p>
        <a href="mailto:security@vantio.ai"
          className="text-sm font-medium text-[--accent] underline underline-offset-4 hover:text-[--accent-dim]">
          security@vantio.ai
        </a>
      </div>
    </main>
  );
}
