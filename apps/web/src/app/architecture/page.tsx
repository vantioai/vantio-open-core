import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Architecture — Vantio AI",
  description: "Three components. One atomic operation. Zero trust required at any layer.",
};

const LAYERS = [
  {
    tier: "RING-0",
    label: "Phantom Engine",
    color: "text-[--accent]", border: "border-[--accent]/30", bg: "bg-[--accent]/5",
    headline: "eBPF Physical Containment",
    body: "Pure Rust eBPF program compiled to bpfel-unknown-none and loaded into the Linux kernel via Aya. Every agent syscall is intercepted at LSM hook boundaries before it can affect the host filesystem, network, or external state. Three program types run simultaneously:",
    points: [
      { code: "sched_process_fork", desc: "BTF tracepoint — inherits trace_id from parent to all child PIDs. LLM agents that spawn bash, curl, or python subprocesses are covered without re-seeding." },
      { code: "ssl_write uprobe",   desc: "Attaches to SSL_write in libssl.so.3. Intercepts the egress memory buffer before encryption — before transmission. Records PID, trace_id, bytes, and target host." },
      { code: "tc_enforce",         desc: "TC egress classifier on the network interface. For traced PIDs, drops packets to non-allowlisted destinations (TC_ACT_SHOT). RFC-1918 ranges matched via bitmask — full CIDR coverage." },
    ],
    deploy: "Kubernetes DaemonSet (one pod per node). Requires CAP_BPF, CAP_NET_ADMIN, CAP_SYS_ADMIN and host PID/network namespaces. Compatible with EKS, GKE, AKS on kernel ≥ 5.8.",
  },
  {
    tier: "RING-3",
    label: "Oracle zkVM",
    color: "text-blue-400", border: "border-blue-400/30", bg: "bg-blue-400/5",
    headline: "Managed Edge Proxy",
    body: "For Tier 02 deployments without kernel access, the Oracle Proxy provides transparent HTTPS interception at the network layer. Update one environment variable — every AI API call passes through real-time policy enforcement:",
    points: [
      { code: "VANTIO_CLOUD_INGEST=true", desc: "Routes all outbound LLM calls through the Managed Edge Proxy without code changes. Non-compliant calls blocked before they reach the model." },
      { code: "vantio_trace_map",         desc: "Pinned BPF map at /sys/fs/bpf/vantio_trace_map. The cross-OS bridge between Windows NT user-space (CLI) and the Linux Ring-0 kernel boundary." },
      { code: "Rate limiting",            desc: "100 requests/minute per API key enforced at Vercel Edge via Upstash Redis — before any Supabase query. Protects infrastructure budget during load spikes." },
    ],
    deploy: "No infrastructure required for Tier 02. Set VANTIO_API_KEY and VANTIO_INGEST_URL — the CLI auto-intercepts Node.js processes via --require injection.",
  },
  {
    tier: "LEDGER",
    label: "Anomaly Record",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    headline: "Cryptographic Compliance Ledger",
    body: "Every enforcement decision produces a TlsSeveranceEvent — a structured, HMAC-signed record committed to the compliance ledger. Two substrate modes:",
    points: [
      { code: "SOVEREIGN_MODE=cloud",    desc: "GCP Spanner TrueTime WORM ledger (allow_commit_timestamp=true). Globally consistent timestamps. The Edge Proxy service account holds strictly append-only INSERT privileges." },
      { code: "SOVEREIGN_MODE=local",    desc: "NDJSON file output (--output-file). Compatible with the gcloud spanner import format for air-gapped environments. Immutable on local disk before upload." },
      { code: "x-vantio-signature",      desc: "HMAC-SHA256 of every ingest payload, signed with the tenant's API key. Events are cryptographically receipted and verifiable without trusting the ledger." },
    ],
    deploy: "schema/spanner_ledger.ddl defines the TrueTimeLedger table. The Edge Proxy service account requires only INSERT privileges — no SELECT, UPDATE, or DELETE.",
  },
];

const STACK = [
  ["eBPF Runtime", "Aya 0.13 (Rust)", "Ring-0 map/program loader"],
  ["eBPF Target", "bpfel-unknown-none", "Bare-metal BPF ELF"],
  ["Kernel min", "Linux 5.8+", "Ring buffer + BTF support"],
  ["User-space", "Tokio async", "Non-blocking ring drain"],
  ["Ledger", "GCP Spanner", "TrueTime WORM + SOVEREIGN_MODE"],
  ["Proxy runtime", "Next.js 15 Edge", "Vercel global edge network"],
  ["Auth", "Supabase magic link", "Zero-password, session-scoped"],
  ["Supply chain", "SLSA Level 3", "Sigstore + Rekor attestation"],
];

export default function ArchitecturePage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-24">
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--accent]">Architecture</p>
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
