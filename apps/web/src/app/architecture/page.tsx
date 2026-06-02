import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Architecture",
  description: "Three components. One atomic operation. Zero trust required at any layer.",
  path: "/architecture",
});

const LAYERS = [
  {
    tier: "RING-0",
    label: "Phantom Engine",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
    headline: "eBPF Physical Containment",
    body: "Pure Rust eBPF programs compiled to bpfel-unknown-none and loaded into the Linux kernel via Aya. Agent activity is intercepted at kernel hook boundaries — tracepoints, uprobes, and a TC egress classifier — before it can affect the host filesystem, network, or external state. The programs run simultaneously:",
    points: [
      { code: "sched_process_fork", desc: "BTF tracepoint — inherits trace_id from parent to all child PIDs. LLM agents that spawn bash, curl, or python subprocesses are covered without re-seeding." },
      { code: "ssl_write uprobe",   desc: "Attaches to SSL_write in libssl.so.3 and gnutls_record_send in libgnutls.so.30. Intercepts the egress buffer before encryption — full TLS coverage across OpenSSL and GnuTLS (the default curl backend on Ubuntu). Records PID, trace_id, bytes, and target host." },
      { code: "execve / openat",    desc: "Syscall tracepoints (sys_enter_execve, sys_enter_openat) attribute every subprocess spawn and file open to a trace_id. Each event carries a type discriminant so it is never confused with a TLS record on the shared ring buffer." },
      { code: "tc_enforce",         desc: "TC egress classifier on the network interface. Drops packets to non-allowlisted destinations (TC_ACT_SHOT) across both IPv4 and IPv6 — RFC-1918 plus IPv6 ULA/link-local matched via bitmask, so resolving an AAAA record cannot bypass enforcement." },
    ],
    deploy: "Kubernetes DaemonSet (one pod per node). Requires CAP_BPF, CAP_NET_ADMIN, CAP_SYS_ADMIN and host PID/network namespaces. Compatible with EKS, GKE, AKS on kernel ≥ 5.8.",
  },
  {
    tier: "RING-3",
    label: "Oracle zkVM",
    color: "text-blue-400", border: "border-blue-400/30", bg: "bg-blue-400/5",
    headline: "SDK-Side Policy Enforcement",
    body: "For Tier 02 deployments without kernel access, Vantio enforces policy inside the customer's own SDK/CLI — not as a network proxy. The cloud stores a policy you control and receives metadata-only telemetry; prompt and completion content never reach Vantio. Set one environment variable and the SDK redacts PII, caps spend, and blocks off-policy hosts locally before any request leaves your environment:",
    points: [
      { code: "VANTIO_CLOUD_INGEST=true", desc: "The SDK pulls your cloud-managed policy from /api/v1/config and enforces it in-process. Outbound LLM calls go directly to the provider — never routed through Vantio." },
      { code: "redact_pii / blocked_hosts", desc: "Policy-driven redaction and host blocking run client-side. Off-policy requests are stopped locally and logged as BLOCKED_HOST — metadata only, no content." },
      { code: "Rate limiting",            desc: "100 requests/minute per API key enforced at Vercel Edge via Upstash Redis — before any Supabase query. Protects infrastructure budget during load spikes." },
    ],
    deploy: "No infrastructure required for Tier 02. Set VANTIO_API_KEY and VANTIO_INGEST_URL — the CLI instruments Node.js processes in-process via --require injection (not a proxy).",
  },
  {
    tier: "LEDGER",
    label: "Anomaly Record",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    headline: "Cryptographic Compliance Ledger",
    body: "Every enforcement decision produces a TlsSeveranceEvent — a structured, HMAC-signed record committed to the compliance ledger. Two substrate modes:",
    points: [
      { code: "SOVEREIGN_MODE=cloud",    desc: "GCP Spanner TrueTime WORM ledger (allow_commit_timestamp=true). Globally consistent timestamps. The ingest service account holds strictly append-only INSERT privileges." },
      { code: "SOVEREIGN_MODE=local",    desc: "NDJSON file output (--output-file). Compatible with the gcloud spanner import format for air-gapped environments. Immutable on local disk before upload." },
      { code: "x-vantio-signature",      desc: "HMAC-SHA256 receipt over the event trace ID, keyed by the tenant's API key and returned on every ingest. Events are cryptographically receipted and verifiable without trusting the ledger." },
    ],
    deploy: "schema/spanner_ledger.ddl defines the TrueTimeLedger table. The ingest service account requires only INSERT privileges — no SELECT, UPDATE, or DELETE.",
  },
];

const STACK = [
  ["eBPF Runtime", "Aya 0.13 (Rust)", "Ring-0 map/program loader"],
  ["eBPF Target", "bpfel-unknown-none", "Bare-metal BPF ELF"],
  ["Kernel min", "Linux 5.8+", "Ring buffer + BTF support"],
  ["User-space", "Tokio async", "Non-blocking ring drain"],
  ["Ledger", "GCP Spanner", "TrueTime WORM + SOVEREIGN_MODE"],
  ["API runtime", "Next.js 15 Edge", "Vercel global edge network"],
  ["Auth", "Supabase magic link", "Zero-password, session-scoped"],
  ["Supply chain", "SLSA Level 3", "Sigstore + Rekor attestation"],
];

export default function ArchitecturePage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-24">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Architecture", path: "/architecture" }])} />
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-[--accent]/30 bg-[--accent]/5 px-3 py-1 text-xs font-semibold text-[--accent]">Tier 01</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-400/30 bg-blue-400/5 px-3 py-1 text-xs font-semibold text-blue-400">Tier 02</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1 text-xs font-semibold text-red-400">Tier 03</span>
      </div>
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Architecture</p>
      <h1 className="mb-4 text-4xl font-bold">The Architecture of Absolute Containment.</h1>
      <p className="mb-20 max-w-2xl text-lg text-[--muted]">
        Three components. One atomic operation. Zero trust required at any layer.
      </p>

      <div className="space-y-10">
        {LAYERS.map((l) => (
          <div key={l.tier} className={`rounded-xl border ${l.border} ${l.bg} p-8`}>
            <div className="mb-6 flex items-start justify-between gap-4">
              <div>
                <span className={`font-mono text-xs ${l.color}`}>{l.tier}</span>
                <h2 className="mt-1 text-2xl font-bold">{l.label}</h2>
                <p className={`text-sm font-medium ${l.color}`}>{l.headline}</p>
              </div>
            </div>
            <p className="mb-6 text-sm text-[--muted]">{l.body}</p>
            <div className="mb-6 space-y-4">
              {l.points.map(({ code, desc }) => (
                <div key={code} className="flex gap-4">
                  <code className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-xs ${l.color} bg-black/20`}>{code}</code>
                  <p className="text-sm text-[--muted]">{desc}</p>
                </div>
              ))}
            </div>
            <p className={`text-xs font-medium ${l.color}`}>Deploy: <span className="font-normal text-[--muted]">{l.deploy}</span></p>
          </div>
        ))}
      </div>

      {/* Stack table */}
      <div className="mt-20">
        <h2 className="mb-6 text-xl font-bold">Technology Stack</h2>
        <div className="overflow-hidden rounded-xl border border-[--border]">
          <table className="w-full text-sm">
            <thead className="bg-[--surface]">
              <tr>
                {["Component", "Technology", "Purpose"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-widest text-[--muted]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[--border]">
              {STACK.map(([c, t, p]) => (
                <tr key={c} className="transition-colors hover:bg-[--surface]">
                  <td className="px-5 py-3 font-medium">{c}</td>
                  <td className="px-5 py-3 font-mono text-xs text-[--accent]">{t}</td>
                  <td className="px-5 py-3 text-[--muted]">{p}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-12 flex gap-4">
        <a href="/enterprise" className="rounded-md bg-[--accent] px-6 py-3 text-sm font-semibold text-black hover:bg-[--accent-dim]">
          Deploy Enterprise Stack
        </a>
        <a href="/developers" className="rounded-md border border-[--border] px-6 py-3 text-sm font-medium text-[--muted] hover:border-[--foreground] hover:text-[--foreground]">
          Start with Free SDK
        </a>
      </div>
    </main>
  );
}
