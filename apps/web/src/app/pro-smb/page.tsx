import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PRO / SMB — Vantio AI Managed Edge Proxy",
  description: "Managed proxy. Zero infrastructure required. Active AI governance without touching your kernel.",
};

export default function ProSmbPage() {
  return (
    <main>
      <section className="mx-auto max-w-5xl px-6 pb-16 pt-24">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-blue-400">Tier 02 — PRO / SMB</p>
        <h1 className="mb-4 text-4xl font-bold">
          Managed proxy.<br />
          <span className="text-blue-400">Zero infrastructure required.</span>
        </h1>
        <p className="mb-10 max-w-2xl text-lg text-[--muted]">
          The Vantio Managed Edge Proxy governs your AI API traffic at the network layer.
          No Kubernetes. No code changes. Update one environment variable and every AI call
          passes through real-time policy enforcement.
        </p>
        <div className="flex flex-wrap gap-3">
          <a href="/pricing" className="rounded-md bg-blue-400 px-6 py-3 text-sm font-semibold text-black hover:bg-blue-300">
            Start 14-Day Trial — $499/mo
          </a>
          <a href="/dashboard" className="rounded-md border border-blue-400/30 px-6 py-3 text-sm font-medium text-blue-400 hover:bg-blue-400/5">
            View Live Dashboard
          </a>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-20">
        <div className="mx-auto max-w-5xl">
          <h2 className="mb-12 text-2xl font-bold">What you get</h2>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {[
              { title: "Transparent HTTPS Interception", body: "Every AI API call routed through the proxy before reaching OpenAI, Anthropic, Cohere, Google Vertex, or AWS Bedrock. Zero changes to your agent code." },
              { title: "5–25ms Routing Latency", body: "Deployed on Vercel's global edge network. The latency addition is negligible for production workloads — far less expensive than post-incident compliance review." },
              { title: "30-day Spanner WORM Log", body: "Every request and governance decision stored in an append-only, cryptographically sealed compliance log. TrueTime timestamps for globally consistent audit trails." },
              { title: "HMAC-Signed Events", body: "Every anomaly record is HMAC-SHA256 signed with your API key. Independently verifiable by any third party without trusting the ledger." },
              { title: "Multi-Provider Routing", body: "Governance endpoints for OpenAI, Anthropic, AWS Bedrock, Google Vertex, and Cohere. One configuration — all providers covered." },
              { title: "Stripe Self-Serve Billing", body: "Subscribe, upgrade, and cancel in the Oracle UI without contacting sales. 14-day free trial. Metered pricing beyond included limits." },
              { title: "Rate Limiting at Edge", body: "100 requests/minute per API key enforced at Vercel Edge via Upstash Redis — before any database query. Infinite-loop agents cannot exhaust your budget." },
              { title: "Slack Alerting", body: "Supabase Database Webhook fires a Slack Block Kit alert on every policy violation — tenant, target host, bytes blocked, trace ID, and a direct link to your dashboard." },
              { title: "Email Support — 24hr SLA", body: "Direct access to the Vantio engineering team. Escalation path to Enterprise for teams that need kernel-level enforcement." },
            ].map(({ title, body }) => (
              <div key={title} className="rounded-xl border border-[--border] bg-[--background] p-5">
                <h3 className="mb-2 text-sm font-semibold text-blue-400">→ {title}</h3>
                <p className="text-xs text-[--muted]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Setup */}
      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="mb-3 text-2xl font-bold">Up in 60 seconds</h2>
        <p className="mb-10 text-[--muted]">From checkout to dashboard telemetry in under 2 minutes.</p>
        <ol className="space-y-6">
          {[
            { n: "01", title: "Start your 14-day trial", body: "Click Start Trial. Stripe Checkout collects your card — no charge for 14 days. Your tenant is provisioned and your API key is generated." },
            { n: "02", title: "Set two env vars", body: "VANTIO_API_KEY=<your key>  VANTIO_INGEST_URL=https://vantio.ai\nThat's it. No infrastructure changes. No Kubernetes. No kernel modules." },
            { n: "03", title: "Run your agent — zero code changes", body: "vantio run node agent.js   or   vantio run python agent.py\nThe CLI auto-intercepts all LLM API calls and routes anomalies to your dashboard." },
            { n: "04", title: "Anomalies surface in real time", body: "Every blocked or flagged call appears on your /dashboard within 50ms. Export CSV for compliance review. Slack alerts for immediate ops awareness." },
          ].map(({ n, title, body }) => (
            <li key={n} className="flex gap-6">
              <span className="mt-1 shrink-0 font-mono text-xs font-bold text-blue-400">{n}</span>
              <div>
                <p className="font-semibold">{title}</p>
                <p className="mt-1 whitespace-pre-line text-sm text-[--muted]">{body}</p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-12 rounded-lg border border-blue-400/20 bg-blue-400/5 p-5 text-xs text-[--muted]">
          <strong className="text-[--foreground]">Layer 7 boundary note:</strong>{" "}
          The PRO / SMB tier operates at the application layer (Ring-3). It intercepts network calls and emits governance telemetry —
          it does not enforce at the kernel level. For bare-metal kernel enforcement, see the{" "}
          <a href="/enterprise" className="text-red-400 underline">Enterprise tier</a>.
        </div>
      </section>
    </main>
  );
}
