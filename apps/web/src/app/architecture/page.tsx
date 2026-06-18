import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { Reveal } from "@/components/reveal";

export const metadata: Metadata = buildMetadata({
  title: "Architecture",
  description: "How Vantio works: three tiers across two Linux privilege rings, each enforcing where it can reach, with one shared cryptographic audit ledger you can verify without trusting us.",
  path: "/architecture",
});

// Tier → layer overview. Tier colors are canonical: 01 green, 02 blue, 03 red,
// and the shared ledger is neutral (violet) because it is not a tier.
const MAP = [
  { tier: "Tier 01", ring: "Ring-3 · SDK", role: "Observe in your SDK", color: "text-[var(--accent)]", border: "border-[var(--accent)]/30" },
  { tier: "Tier 02", ring: "Ring-3 · SDK", role: "Enforce in your SDK", color: "text-blue-400", border: "border-blue-400/30" },
  { tier: "Tier 03", ring: "Ring-0 · Kernel", role: "Enforce in the kernel", color: "text-red-400", border: "border-red-400/30" },
  { tier: "Ledger", ring: "Shared", role: "One signed audit record", color: "text-violet-300", border: "border-violet-400/30" },
];

const LAYERS = [
  {
    tier: "Tier 01",
    ring: "Ring-3 · SDK · observe-only",
    label: "Agent SDK — Observe",
    color: "text-[var(--accent)]", border: "border-[var(--accent)]/30", bg: "bg-[var(--accent)]/5",
    headline: "SDK-Side Observability (Observe-Only)",
    body: "The free, open-source SDK runs in-process in user-space (Ring-3). It wraps any agent call with shield(), threads a trace_id through the full async call-tree, and emits metadata-only telemetry. This is the SAME SDK as Tier 02 with enforcement switched off — it observes and reports, it never blocks. Prompt and completion content never leave your environment.",
    points: [
      { code: "shield() / getCurrentTraceId", desc: "Wraps any async agent call and generates a VANTIO_TRACE_ID, propagated via AsyncLocalStorage to every async hop and spawned child call — no monkey-patching, no AST modification, no global state." },
      { code: "reportAnomaly()",              desc: "Emits structured, metadata-only events (target_host, bytes_severed, pid, action_taken). Zero linguistic content ever reaches the ledger; prompts and completions are architecturally excluded." },
      { code: "observe-only",                 desc: "No policy is fetched and nothing is blocked — the SDK records what happened. Turn on Tier 02 to make the very same SDK enforce client-side." },
    ],
    deploy: "npm i @vantio/agent-sdk or pip install vantio-agent-sdk. Set VANTIO_API_KEY — 10,000 events/month free. No infrastructure, no proxy, no code changes.",
  },
  {
    tier: "Tier 02",
    ring: "Ring-3 · SDK · enforce",
    label: "Oracle Policy Plane",
    color: "text-blue-400", border: "border-blue-400/30", bg: "bg-blue-400/5",
    headline: "SDK-Side Policy Enforcement",
    body: "For Tier 02 deployments without kernel access, Vantio enforces policy inside the customer's own SDK/CLI — not as a network proxy. The cloud stores a policy you control and receives metadata-only telemetry; prompt and completion content never reach Vantio. Set one environment variable and the SDK redacts PII, caps spend, and blocks off-policy hosts locally before any request leaves your environment:",
    points: [
      { code: "VANTIO_CLOUD_INGEST=true", desc: "The SDK pulls your cloud-managed policy from /api/v1/config and enforces it in-process. Outbound LLM calls go directly to the provider — never routed through Vantio. If the policy fetch fails, the SDK fails open and observes only." },
      { code: "redact_pii / blocked_hosts", desc: "Policy-driven redaction and host blocking run client-side. blocked_hosts/allowed_hosts apply to any named host (not just known LLMs); off-policy requests are stopped locally and logged as BLOCKED_HOST — metadata only, no content." },
      { code: "Rate limiting",            desc: "100 requests/minute per API key enforced at Vercel Edge via Upstash Redis — before any Supabase query. Protects infrastructure budget during load spikes." },
    ],
    deploy: "No infrastructure required for Tier 02. Set VANTIO_API_KEY and VANTIO_INGEST_URL — the CLI instruments Node.js processes in-process via NODE_OPTIONS (--require) injection, not a proxy. Enforcement fails open if the control plane is unreachable — a Vantio outage never blocks your agent.",
  },
  {
    tier: "Tier 03",
    ring: "Ring-0 · Kernel",
    label: "Phantom Engine",
    color: "text-red-400", border: "border-red-400/30", bg: "bg-red-400/5",
    headline: "eBPF Kernel Enforcement",
    body: "Pure Rust eBPF programs compiled to bpfel-unknown-none and loaded into the Linux kernel via Aya. Only enrolled workloads — matched by cgroup via Kubernetes labels/annotations — are enforced; all other host traffic is passed through untouched. For enrolled agents, activity is intercepted at kernel hook boundaries — tracepoints, uprobes, and a TC egress classifier — before it can affect the host filesystem, network, or external state. The programs run simultaneously:",
    points: [
      { code: "sched_process_fork", desc: "BTF tracepoint — inherits trace_id from parent to all child PIDs. LLM agents that spawn bash, curl, or python subprocesses are covered without re-seeding." },
      { code: "ssl_write uprobe",   desc: "Attaches to SSL_write in libssl.so.3 and gnutls_record_send in libgnutls.so.30. Intercepts the egress buffer before encryption — full TLS coverage across OpenSSL and GnuTLS (the default curl backend on Ubuntu). Records PID, trace_id, bytes, and target host." },
      { code: "execve / openat",    desc: "Syscall tracepoints (sys_enter_execve, sys_enter_openat) attribute every subprocess spawn and file open to a trace_id. Each event carries a type discriminant so it is never confused with a TLS record on the shared ring buffer." },
      { code: "tc_enforce",         desc: "TC egress classifier on the network interface. For enrolled cgroups, drops packets to non-allowlisted destinations (TC_ACT_SHOT) across both IPv4 and IPv6 — RFC-1918 plus IPv6 ULA/link-local matched via bitmask, so resolving an AAAA record cannot bypass enforcement. Traffic from unenrolled workloads is never dropped." },
      { code: "Shadow AI detection", desc: "Any process on an enrolled node that initiates outbound traffic to a known LLM endpoint (OpenAI, Anthropic, Bedrock, etc.) without a valid trace_id is flagged — including processes that have no SDK instrumentation at all. This maps your full AI attack surface, not just the agents your team officially deployed." },
    ],
    deploy: "De-privileged Kubernetes DaemonSet (one pod per node) or bare-metal Linux. Runs with minimal Linux capabilities (CAP_BPF, CAP_NET_ADMIN), a seccomp profile, and a read-only root filesystem. Per-agent enrollment via Kubernetes labels/annotations. Compatible with EKS, GKE, AKS on kernel ≥ 5.8.",
  },
  {
    tier: "Shared",
    ring: "All tiers · compliance substrate",
    label: "Anomaly Record",
    color: "text-violet-300", border: "border-violet-400/25", bg: "bg-violet-400/5",
    headline: "Cryptographic Compliance Ledger",
    body: "A shared component written by every tier. Every event — observed, allowed, redacted, or blocked — is committed to the compliance ledger as a structured, HMAC-signed, metadata-only record. Two substrate modes:",
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
  ["Shadow AI detection", "eBPF process monitoring", "Flags unenrolled processes calling LLM endpoints"],
];

export default function ArchitecturePage() {
  return (
    <main className="relative mx-auto max-w-5xl px-6 py-24">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Architecture", path: "/architecture" }])} />
      <div className="pointer-events-none absolute left-1/2 top-0 h-72 w-[640px] -translate-x-1/2 rounded-full bg-[var(--accent)]/5 blur-3xl" />

      <div className="relative">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">Architecture</p>
        <h1 className="mb-4 text-4xl font-bold">The Architecture of Verifiable Enforcement.</h1>
        <p className="mb-12 max-w-2xl text-lg text-[var(--muted)]">
          Three tiers, two privilege rings. Each tier enforces where it can reach. All three share one
          cryptographic audit record you can verify yourself — without having to trust us.
        </p>

        {/* How tiers map to layers */}
        <div className="mb-20 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
          <p className="mb-5 text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">How tiers map to layers</p>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {MAP.map((m) => (
              <div key={m.tier} className={`rounded-xl border ${m.border} bg-[var(--surface-2)] p-4`}>
                <div className="flex items-center justify-between gap-2">
                  <span className={`font-mono text-xs font-bold ${m.color}`}>{m.tier}</span>
                  <span className="rounded-full border border-[var(--border-2)] px-2 py-0.5 font-mono text-[10px] text-[var(--muted)]">{m.ring}</span>
                </div>
                <p className="mt-2 text-sm font-medium text-[var(--foreground)]">{m.role}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="relative space-y-10">
        {LAYERS.map((l) => (
          <Reveal key={l.tier} className="h-full">
            <div className={`lift rounded-xl border ${l.border} ${l.bg} p-8`}>
              <div className="mb-6">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`rounded-full border ${l.border} px-2.5 py-0.5 font-mono text-xs font-bold ${l.color}`}>{l.tier}</span>
                  <span className="rounded-full border border-[var(--border-2)] bg-[var(--surface-2)] px-2.5 py-0.5 font-mono text-[10px] text-[var(--muted)]">{l.ring}</span>
                </div>
                <h2 className="mt-3 text-2xl font-bold">{l.label}</h2>
                <p className={`text-sm font-medium ${l.color}`}>{l.headline}</p>
              </div>
              <p className="mb-6 text-sm text-[var(--muted)]">{l.body}</p>
              <div className="mb-6 space-y-4">
                {l.points.map(({ code, desc }) => (
                  <div key={code} className="flex gap-4">
                    <code className={`mt-0.5 shrink-0 rounded bg-black/20 px-2 py-0.5 text-xs ${l.color}`}>{code}</code>
                    <p className="text-sm text-[var(--muted)]">{desc}</p>
                  </div>
                ))}
              </div>
              <p className={`text-xs font-medium ${l.color}`}>Deploy: <span className="font-normal text-[var(--muted)]">{l.deploy}</span></p>
            </div>
          </Reveal>
        ))}
      </div>

      {/* Stack table */}
      <div className="relative mt-20">
        <h2 className="mb-6 text-xl font-bold">Technology Stack</h2>
        <div className="overflow-hidden rounded-xl border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--surface)]">
              <tr>
                {["Component", "Technology", "Purpose"].map((h) => (
                  <th key={h} className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-widest text-[var(--muted)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {STACK.map(([c, t, p]) => (
                <tr key={c} className="transition-colors hover:bg-[var(--surface)]">
                  <td className="px-5 py-3 font-medium">{c}</td>
                  <td className="px-5 py-3 font-mono text-xs text-[var(--accent)]">{t}</td>
                  <td className="px-5 py-3 text-[var(--muted)]">{p}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="relative mt-12 flex flex-wrap gap-4">
        <a href="/developers" className="rounded-md bg-[var(--accent)] px-6 py-3 text-sm font-semibold text-black transition-colors hover:bg-[var(--accent-dim)]">
          Start with the Free SDK
        </a>
        <a href="/enterprise" className="rounded-md border border-red-400/30 px-6 py-3 text-sm font-medium text-red-400 transition-colors hover:bg-red-400/10">
          Deploy the Enterprise Stack →
        </a>
      </div>
    </main>
  );
}
