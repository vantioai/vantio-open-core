import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Enterprise — Vantio AI",
  description: "The only AI governance product that enforces at the operating system kernel level. Your agents literally cannot exfiltrate data.",
};

const DIFFERENTIATORS = [
  {
    label: "No other product does this",
    title: "Enforcement happens below your application",
    body: "Every other AI governance tool operates at the application layer — they read what your agent says and decide whether to allow it. Vantio's Phantom Engine operates at Ring-0, the OS kernel level. Your agent's code never even gets to execute the unauthorized action. The kernel drops the packet before it leaves the machine.",
    code: "TC_ACT_SHOT at the kernel boundary\nBefore encryption · Before transmission\nYour agent cannot bypass this layer",
  },
  {
    label: "Cryptographically provable",
    title: "Every decision comes with a mathematical proof",
    body: "Vantio's Anomaly Records aren't just logs — they're cryptographically signed records committed to a TrueTime-stamped, append-only ledger. Every enforcement decision is independently verifiable by any third party without trusting Vantio or your infrastructure. This is what regulators and auditors need.",
    code: "HMAC-SHA256 signed per event\nTrueTime timestamps (GCP Spanner)\nImmutable · Append-only · WORM",
  },
  {
    label: "Child process inheritance",
    title: "AI agents can't escape by spawning subprocesses",
    body: "Most enforcement tools only track the parent process. Vantio's BTF tracepoint on sched_process_fork propagates the trace context to every child process automatically — bash, curl, python, any subprocess your agent spawns is tracked under the same governance policy, with no re-instrumentation required.",
    code: "sched_process_fork BTF tracepoint\nPID inheritance across all children\nNo re-seeding · No gaps in coverage",
  },
  {
    label: "Sovereign deployment",
    title: "Your anomaly records never leave your VPC",
    body: "Enterprise deployments run entirely inside your own Kubernetes cluster via Helm. The enforcement layer deploys as a DaemonSet on every node. Anomaly records are committed to your own GCP Spanner instance or a local air-gapped substrate. Vantio has zero access to your data.",
    code: "helm install vantio-phantom-engine .\nDaemonSet on every node\nYour Spanner · Your VPC · Your data",
  },
];

const COMPLIANCE = [
  { standard: "SEC Rule 17a-4", detail: "7-year WORM retention with TrueTime timestamps" },
  { standard: "MiFID II Article 25", detail: "Globally consistent audit timeline" },
  { standard: "SOC 2 CC6.1 / CC6.2", detail: "Dual-authorization controls + immutable audit logs" },
  { standard: "HIPAA §164.312", detail: "Infrastructure-layer enforcement prevents ePHI exfiltration" },
  { standard: "GDPR Article 30", detail: "Records of processing activities by design" },
  { standard: "NIST CSF PR.AC-4", detail: "Least-privilege enforcement at the kernel layer" },
];

export default function EnterprisePage() {
  return (
    <main>
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-24 pt-28">
        <div className="pointer-events-none absolute left-1/2 top-0 h-96 w-[600px] -translate-x-1/2 rounded-full bg-red-500/6 blur-3xl" />
        <div className="relative mx-auto max-w-4xl text-center">
          <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-red-400/30 bg-red-400/5 px-4 py-1.5 text-xs font-semibold text-red-400">
            Tier 03 — Enterprise
          </span>
          <h1 className="mt-4 text-5xl font-bold leading-tight tracking-tight lg:text-6xl">
            The only AI governance that
            <span className="block bg-gradient-to-r from-red-400 via-orange-300 to-red-400 bg-clip-text text-transparent">
              enforces at Ring-0.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-[--muted]">
            Every other product reads your agent&apos;s output and calls it governance.
            Vantio&apos;s Phantom Engine attaches to the Linux kernel — before your agent can
            make a network call, open a file, or spawn a subprocess. The boundary is
            physical, not logical.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link href="/auth/enterprise"
              className="rounded-xl bg-red-500 px-7 py-3.5 text-sm font-bold text-white shadow-lg shadow-red-500/20 transition-all hover:bg-red-400 hover:shadow-red-500/30">
              Request Architecture Review
            </Link>
            <Link href="/architecture"
              className="rounded-xl border border-[--border-2] bg-[--surface] px-7 py-3.5 text-sm font-medium text-[--muted] transition-all hover:border-[--border] hover:text-[--foreground]">
              View Technical Architecture →
            </Link>
          </div>

          {/* Stat bar */}
          <div className="mt-14 grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-[--border] bg-[--border] md:grid-cols-4">
            {[
              { v: "< 1ms",    l: "Enforcement latency" },
              { v: "Ring-0",   l: "Kernel enforcement level" },
              { v: "7 years",  l: "WORM audit retention" },
              { v: "0",        l: "Bytes of your data we store" },
            ].map(({ v, l }) => (
              <div key={l} className="bg-[--surface-2] px-6 py-5 text-center">
                <p className="text-2xl font-black text-red-400">{v}</p>
                <p className="mt-0.5 text-xs text-[--muted]">{l}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* What makes it unique */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-red-400">Why There Is No Comparable Product</p>
          <h2 className="mb-3 text-3xl font-bold">Four capabilities no one else has.</h2>
          <p className="mb-14 max-w-2xl text-[--muted]">
            Building kernel-level enforcement for AI agents requires expertise across eBPF, Rust,
            distributed systems, and cryptography simultaneously. This is why no AI safety
            startup has done it before.
          </p>
          <div className="space-y-6">
            {DIFFERENTIATORS.map(({ label, title, body, code }) => (
              <div key={title} className="overflow-hidden rounded-2xl border border-red-400/15 bg-[--surface-2]">
                <div className="grid md:grid-cols-2">
                  <div className="p-7">
                    <span className="mb-3 inline-block rounded-full border border-red-400/30 bg-red-400/10 px-3 py-0.5 text-xs font-semibold text-red-400">
                      {label}
                    </span>
                    <h3 className="mb-3 text-lg font-bold">{title}</h3>
                    <p className="text-sm leading-relaxed text-[--muted]">{body}</p>
                  </div>
                  <div className="flex items-center border-t border-red-400/10 bg-[--surface] p-7 md:border-l md:border-t-0">
                    <pre className="font-mono text-xs leading-relaxed text-red-300/80">
                      <code>{code}</code>
                    </pre>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Deployment */}
      <section className="px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-10 md:grid-cols-2">
            <div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Deployment</p>
              <h2 className="mb-5 text-3xl font-bold">Kubernetes Native.<br />Your Cluster. Your VPC.</h2>
              <p className="mb-6 text-[--muted]">
                The Vantio Enterprise Helm chart deploys the complete Phantom Engine into
                your existing GKE, EKS, or AKS cluster. The enforcement layer runs as a
                privileged DaemonSet on every node. Anomaly Records are stored in your
                own database — Vantio has zero access.
              </p>
              <div className="space-y-3">
                {[
                  "helm install vantio-phantom-engine . --set enforce=true",
                  "One DaemonSet pod per node — automatic coverage",
                  "Compatible with GKE, EKS, AKS, bare metal",
                  "Linux kernel ≥ 5.8 with BTF enabled",
                ].map((l) => (
                  <div key={l} className="flex items-start gap-2 text-sm">
                    <span className="mt-0.5 text-red-400">→</span>
                    <span className="font-mono text-xs text-[--muted]">{l}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="overflow-hidden rounded-2xl border border-[--border] bg-[--surface]">
              <div className="flex items-center gap-1.5 border-b border-[--border] bg-[--surface-2] px-4 py-2.5">
                <span className="h-2.5 w-2.5 rounded-full bg-red-500/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/60" />
                <span className="h-2.5 w-2.5 rounded-full bg-green-500/60" />
                <span className="ml-2 text-xs text-[--muted]">helm install</span>
              </div>
              <div className="p-5 font-mono text-xs leading-loose text-[--muted]">
                <p><span className="text-red-400">$</span> helm install vantio \</p>
                <p className="pl-4">vantio/phantom-engine \</p>
                <p className="pl-4">--set nodeIface=ens5 \</p>
                <p className="pl-4">--set enforce=true \</p>
                <p className="pl-4">--set sovereignMode=cloud \</p>
                <p className="pl-4">--set spannerDatabase=projects/...</p>
                <p className="mt-3 text-green-400">✓ DaemonSet deployed to 12 nodes</p>
                <p className="text-green-400">✓ vantio_trace_map pinned at /sys/fs/bpf/</p>
                <p className="text-green-400">✓ SSL_write uprobe attached (libssl.so.3)</p>
                <p className="text-green-400">✓ TC enforcement active on ens5</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Compliance */}
      <section className="border-t border-[--border] bg-[--surface] px-6 py-24">
        <div className="mx-auto max-w-5xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--muted]">Compliance</p>
          <h2 className="mb-4 text-3xl font-bold">Designed for regulated industries.</h2>
          <p className="mb-10 text-[--muted]">Vantio satisfies the most demanding regulatory requirements by design — not through manual controls or policy documents.</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {COMPLIANCE.map(({ standard, detail }) => (
              <div key={standard} className="rounded-xl border border-[--border] bg-[--surface-2] p-4">
                <p className="mb-1 text-sm font-semibold text-red-400">{standard}</p>
                <p className="text-xs text-[--muted]">{detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-6 py-24 text-center">
        <div className="mx-auto max-w-2xl">
          <h2 className="mb-3 text-3xl font-bold">Every Enterprise deployment begins with a technical architecture review.</h2>
          <p className="mb-2 text-[--muted]">Custom SLA, dedicated engineering support, and onboarding are included. Pricing from $50,000 ARR.</p>
          <p className="mb-8 text-xs text-[--muted]">The Phantom Engine requires CAP_BPF, CAP_NET_ADMIN, and CAP_SYS_ADMIN. Deployment requires cluster-admin access and must be reviewed by your platform security team.</p>
          <Link href="/auth/enterprise"
            className="inline-flex items-center gap-2 rounded-xl bg-red-500 px-8 py-4 text-sm font-bold text-white shadow-lg shadow-red-500/20 transition-all hover:bg-red-400">
            Request Architecture Review →
          </Link>
        </div>
      </section>
    </main>
  );
}
