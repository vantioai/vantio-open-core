import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Vantio AI — Deterministic AI Governance",
  description:
    "Cloud-managed telemetry governance for autonomous LLM agents. Route anomaly events to a tamper-evident ledger — no infrastructure required.",
};

export default function HomePage() {
  return (
    <main className="min-h-screen bg-white">
      {/* Hero */}
      <section className="mx-auto max-w-4xl px-6 pb-20 pt-24 text-center">
        <p className="mb-4 inline-flex items-center gap-2 rounded-full border border-gray-200 px-3 py-1 text-xs font-semibold uppercase tracking-widest text-gray-500">
          <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
          Open-Core · Cloud-Managed
        </p>
        <h1 className="mt-4 text-5xl font-bold tracking-tight text-gray-900 sm:text-6xl">
          Your AI agents run.<br />
          <span className="text-gray-400">Nothing leaks.</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-gray-500">
          Vantio wraps your autonomous LLM agents in a cryptographic trace context
          and routes anomaly telemetry to a tamper-evident cloud ledger — no
          infrastructure, no kernel configuration, no ops burden.
        </p>
        <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <a
            href="/pricing"
            className="rounded-lg bg-gray-900 px-8 py-3.5 text-sm font-semibold text-white transition-colors hover:bg-gray-700"
          >
            Start Free Trial — $499/mo
          </a>
          <a
            href="https://github.com/vantioai/vantio-open-core"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-lg border border-gray-300 px-8 py-3.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-gray-50"
          >
            View Open-Core SDK →
          </a>
        </div>
      </section>

      {/* How it works */}
      <section className="border-t border-gray-100 bg-gray-50 px-6 py-20">
        <div className="mx-auto max-w-4xl">
          <p className="mb-3 text-center text-xs font-semibold uppercase tracking-widest text-gray-400">
            How it works
          </p>
          <h2 className="mb-12 text-center text-3xl font-bold text-gray-900">
            Three lines of code. Full observability.
          </h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {[
              {
                step: "01",
                title: "Wrap your agent",
                body: "Add withVantio() from @vantio/agent-sdk. A cryptographic VANTIO_TRACE_ID is generated and propagated through every async hop — no AST modifications, no monkey-patching.",
                code: `await withVantio(async () => {\n  await runMyAgent();\n});`,
              },
              {
                step: "02",
                title: "Report anomalies",
                body: "Call reportAnomaly() with execution metadata — bytes, target host, PID. Zero linguistic content ever leaves your process. The payload is severed before this call.",
                code: `await reportAnomaly({\n  bytes_severed: 14382,\n  target_host:\n    "api.openai.com",\n  action_taken: "POLICY_VIOLATION",\n});`,
              },
              {
                step: "03",
                title: "Ledger records",
                body: "With VANTIO_CLOUD_INGEST=true, the metadata routes to your Managed Edge Proxy and appears on your dashboard in real time. 90-day WORM retention included.",
                code: `anomaly_metadata: {\n  bytes_severed: 14382,\n  target_host:\n    "api.openai.com",\n  audit_mode: true\n}`,
              },
            ].map(({ step, title, body, code }) => (
              <div key={step} className="rounded-xl border border-gray-200 bg-white p-6">
                <span className="font-mono text-xs font-bold text-gray-300">{step}</span>
                <h3 className="mt-3 font-semibold text-gray-900">{title}</h3>
                <p className="mt-2 text-sm text-gray-500">{body}</p>
                <pre className="mt-4 overflow-x-auto rounded-lg bg-gray-950 p-3 text-xs text-gray-300">
                  <code>{code}</code>
                </pre>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Enterprise callout */}
      <section className="border-t border-gray-100 px-6 py-16">
        <div className="mx-auto max-w-3xl rounded-2xl border border-gray-200 bg-gray-50 p-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
            Need Ring-0 enforcement?
          </p>
          <h3 className="mt-2 text-xl font-bold text-gray-900">
            The Phantom Engine is an Enterprise feature.
          </h3>
          <p className="mx-auto mt-3 max-w-xl text-sm text-gray-500">
            For Fortune 500 and regulated institutions, Vantio Enterprise deploys
            a pure-Rust eBPF hypervisor that intercepts{" "}
            <code className="rounded bg-gray-100 px-1 text-xs">SSL_write</code> at
            the kernel boundary — before encryption, before transmission.
            Payload severance happens at Ring-0, not the application layer.
          </p>
          <a
            href="/auth/enterprise"
            className="mt-6 inline-block rounded-lg border border-gray-300 px-6 py-2.5 text-sm font-semibold text-gray-700 transition-colors hover:bg-white"
          >
            Contact Enterprise Sales →
          </a>
        </div>
      </section>

      {/* Social proof anchors */}
      <section className="px-6 py-16">
        <div className="mx-auto max-w-3xl text-center">
          <p className="mb-8 text-xs font-semibold uppercase tracking-widest text-gray-400">
            Built for regulated production environments
          </p>
          <div className="flex flex-wrap justify-center gap-8 text-sm font-medium text-gray-400">
            {[
              "SLSA Level 3 Supply Chain",
              "SOC 2 Type II Architecture",
              "Delaware C-Corporation",
              "ISO 27001 / NIST CSF",
              "Zero linguistic retention",
            ].map((label) => (
              <span key={label} className="flex items-center gap-2">
                <span className="text-green-500">✓</span> {label}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA strip */}
      <section className="border-t border-gray-100 bg-gray-900 px-6 py-16 text-center text-white">
        <h2 className="text-3xl font-bold">Ready to enforce your boundary?</h2>
        <p className="mx-auto mt-3 max-w-xl text-gray-400">
          $499/month. 10 seats. Managed Edge Proxy. Cancel anytime.
        </p>
        <Link
          href="/pricing"
          className="mt-8 inline-block rounded-lg bg-white px-8 py-3.5 text-sm font-semibold text-gray-900 transition-colors hover:bg-gray-100"
        >
          See Pricing →
        </Link>
      </section>
    </main>
  );
}
