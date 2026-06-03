import type { Metadata } from "next";
import Link from "next/link";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Enterprise",
  description: "Deploy AI agents in the most regulated industries — kernel-level (eBPF) enforcement for the workloads you enroll, running inside your own cloud, with audit-ready proof for every decision and zero data leaving your walls.",
  path: "/enterprise",
});

const DIFFERENTIATORS = [
  {
    label: "Built in, not bolted on",
    title: "Enforcement in the Linux kernel",
    body: "Most AI safety tools just read what your agent says and hope to catch problems in time. Vantio enforces your rules in the Linux kernel (eBPF) for the workloads you enroll — so even if user-space controls are bypassed, an enrolled agent's off-policy network calls are dropped before they leave the node.",
    code: "Enforces the workloads you enroll\nOff-policy egress dropped in-kernel\nSurvives user-space bypass attempts",
  },
  {
    label: "Audit-ready by design",
    title: "Proof regulators actually accept",
    body: "Every decision Vantio makes is committed to a WORM-compliant audit ledger and sealed with an HMAC-SHA256 receipt — independently verifiable by anyone holding your tenant key, without having to trust us. Hand it straight to an auditor, a regulator, or your board.",
    code: "Every event HMAC-signed + time-stamped\nWORM ledger on GCP Spanner\nVerifiable with your tenant key",
  },
  {
    label: "Subprocess coverage",
    title: "Follows every process an enrolled agent spawns",
    body: "When an enrolled agent kicks off other programs or background tasks, those usually slip right past monitoring tools. Vantio inherits enrollment to every child process, so the subprocesses an enrolled agent spawns stay under the same policy — no re-instrumentation required.",
    code: "Child processes inherit enrollment\nSubprocess egress stays in policy\nNo re-instrumentation needed",
  },
  {
    label: "Your cloud, your data",
    title: "Runs entirely inside your environment",
    body: "Enterprise deployments live inside your own cloud, and your records stay in your own database. Vantio never sees or stores a single byte of your data — real sovereignty for teams that can't send data anywhere.",
    code: "Deploys inside your own cloud\nYour data never leaves your walls\nZero access for Vantio",
  },
];

const COMPLIANCE = [
  { standard: "SEC Rule 17a-4", detail: "7-year WORM retention with TrueTime timestamps" },
  { standard: "MiFID II Article 25", detail: "Globally consistent audit timeline" },
  { standard: "SOC 2 CC6.1 / CC6.2", detail: "Dual-authorization controls + immutable audit logs" },
  { standard: "HIPAA §164.312", detail: "Kernel-level egress enforcement for enrolled workloads handling ePHI" },
  { standard: "GDPR Article 30", detail: "Records of processing activities by design" },
  { standard: "NIST CSF PR.AC-4", detail: "Least-privilege enforcement at the kernel layer" },
];

export default function EnterprisePage() {
  return (
    <main>
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Enterprise", path: "/enterprise" }])} />
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-24 pt-28">
        <div className="pointer-events-none absolute left-1/2 top-0 h-96 w-[600px] -translate-x-1/2 rounded-full bg-red-500/6 blur-3xl" />
        <div className="relative mx-auto max-w-4xl text-center">
          <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-red-400/30 bg-red-400/5 px-4 py-1.5 text-xs font-semibold text-red-400">
            Tier 03 — Enterprise
          </span>
          <h1 className="mt-4 text-5xl font-bold leading-tight tracking-tight lg:text-6xl">
            Go autonomous in the most
            <span className="block bg-gradient-to-r from-red-400 via-orange-300 to-red-400 bg-clip-text text-transparent">
              regulated industries on earth.
            </span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-[--muted]">
            Banks, hospitals, and governments can&apos;t afford an AI agent that colors outside
            the lines. Vantio gives you kernel-level enforcement for the AI workloads you
            enroll — running inside your own cloud on Linux nodes or Kubernetes, with
            audit-ready proof for every decision and zero data ever leaving your walls.
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
              { v: "< 1ms",    l: "Added delay for your agents" },
              { v: "eBPF",     l: "In-kernel enforcement layer" },
              { v: "7 years",  l: "Tamper-proof audit retention" },
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
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-red-400">Why Enterprise Is Different</p>
          <h2 className="mb-3 text-3xl font-bold">Four capabilities that set Enterprise apart.</h2>
          <p className="mb-14 max-w-2xl text-[--muted]">
            Real kernel-level enforcement for AI agents is genuinely hard to build. Here&apos;s what
            that means for you, in plain terms.
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
              <h2 className="mb-5 text-3xl font-bold">Runs in your cloud.<br />Owned by your team.</h2>
              <p className="mb-6 text-[--muted]">
                Vantio Enterprise deploys as a de-privileged DaemonSet on your Linux nodes or
                Kubernetes cluster and enforces the workloads you enroll. Your audit records
                stay in your own database — Vantio never has access to your data. And your
                security team reviews everything before a single agent goes live.
              </p>
              <div className="space-y-3">
                {[
                  "Deploys on bare-metal Linux or Kubernetes — AWS, Google Cloud, or Azure",
                  "Per-agent enrollment via Kubernetes labels and annotations",
                  "De-privileged DaemonSet — minimal Linux caps, seccomp, read-only root filesystem",
                  "Your engineers stay in control; our team supports every step",
                  "Your data and audit records never leave your walls",
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
                <p className="pl-4">--set enroll.selector=vantio.ai/enforce=true \</p>
                <p className="pl-4">--set sovereignMode=cloud \</p>
                <p className="pl-4">--set spannerDatabase=projects/...</p>
                <p className="mt-3 text-green-400">✓ De-privileged DaemonSet deployed to 12 nodes</p>
                <p className="text-green-400">✓ vantio_trace_map pinned at /sys/fs/bpf/</p>
                <p className="text-green-400">✓ SSL_write + gnutls_record_send uprobes attached</p>
                <p className="text-green-400">✓ TC enforcement scoped to enrolled cgroups (IPv4 + IPv6)</p>
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
          <p className="mb-10 text-[--muted]">Vantio maps directly to the controls behind the most demanding regulatory frameworks — enforced in infrastructure, not just policy documents.</p>
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
          <p className="mb-2 text-[--muted]">Includes a custom SLA, dedicated engineering support, and white-glove onboarding. Pricing from $50,000/year.</p>
          <p className="mb-8 text-xs text-[--muted]">Your platform and security teams review and approve everything before anything goes live — nothing is installed without your sign-off.</p>
          <Link href="/auth/enterprise"
            className="inline-flex items-center gap-2 rounded-xl bg-red-500 px-8 py-4 text-sm font-bold text-white shadow-lg shadow-red-500/20 transition-all hover:bg-red-400">
            Request Architecture Review →
          </Link>
        </div>
      </section>
    </main>
  );
}
