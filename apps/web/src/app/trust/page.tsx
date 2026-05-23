import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Trust & Compliance — Vantio AI",
  description:
    "Corporate governance, entity structure, and compliance infrastructure for enterprise procurement.",
};

export default function TrustPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10 space-y-2 border-b border-gray-200 pb-8">
        <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
          Vantio AI, Inc. — Compliance Ledger
        </p>
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">
          Trust &amp; Compliance
        </h1>
      </header>

      <section className="space-y-6 text-gray-700">
        <h2 className="text-xl font-semibold text-gray-900">
          Corporate Governance &amp; Entity Structure
        </h2>
        <p className="leading-relaxed">
          Vantio AI, Inc. operates as a registered Delaware C-Corporation,
          explicitly structured to meet the rigid procurement, vendor risk
          management (VRM), and liability frameworks of Fortune 500
          institutions. Our legal architecture is mapped directly to our
          deterministic security infrastructure. Utilizing an SLSA Level 3
          compliant CI/CD supply chain and pure-Rust eBPF containment, our
          corporate governance ensures absolute structural stability for
          multi-year enterprise infrastructure deployments, satisfying the
          stringent due diligence requirements of Tier-1 capital allocators and
          global enterprise compliance officers.
        </p>
      </section>

      <section className="mt-12 space-y-4 rounded-lg border border-gray-200 bg-gray-50 p-6 text-sm text-gray-600">
        <h3 className="font-semibold text-gray-800">Key Compliance Signals</h3>
        <ul className="list-inside list-disc space-y-2">
          <li>Delaware C-Corporation — SEC &amp; EDGAR-addressable entity</li>
          <li>SLSA Level 3 CI/CD supply-chain attestation</li>
          <li>Pure-Rust eBPF containment layer</li>
          <li>SOC 2 Type II audit-ready architecture</li>
          <li>
            Fortune 500 VRM framework alignment (ISO 27001 / NIST CSF mapping)
          </li>
        </ul>
      </section>
    </main>
  );
}
