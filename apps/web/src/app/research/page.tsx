import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";

export const metadata: Metadata = buildMetadata({
  title: "Research — Engineering Dossiers",
  description: "Engineering dossiers documenting Vantio's technical architecture across the AI governance market.",
  path: "/research",
});

const TIER_STYLE: Record<string, { badge: string; border: string; bg: string; label: string }> = {
  "03": { badge: "text-red-400",   border: "border-red-400/20",  bg: "bg-red-400/5",   label: "Tier 03 — Enterprise" },
  "02": { badge: "text-blue-400",  border: "border-blue-400/20", bg: "bg-blue-400/5",  label: "Tier 02 — Pro" },
  "01": { badge: "text-[--accent]",border: "border-[--accent]/20",bg: "bg-[--accent]/5",label: "Tier 01 — Developer" },
};

const DOSSIERS = [
  {
    id: "01", tier: "03",
    title: "Linguistics Cannot Secure Compute",
    sub: "A post-mortem on why semantic NLP firewalls fail against autonomous agents — infinite semantic evasion, latency attack surfaces, and why physics-based syscall interception is the only verifiable containment primitive.",
    body: `Every semantic guardrail system operates on the same flawed assumption: that the dangerous content of an AI agent's action can be reliably detected by reading the text associated with it. This assumption fails catastrophically against autonomous agents for three compounding reasons.

First, semantic evasion is infinite. Any NLP classifier with a finite parameter space can be bypassed by a sufficiently creative prompt — and autonomous agents can iterate on prompt construction faster than guardrail systems can update their models. The attack surface is unbounded.

Second, the inspection point is wrong. By the time a semantic guardrail reads the model's output, the harmful action may already be in flight. A network call, a file write, a process spawn — these occur at the syscall layer, milliseconds before any application-layer guardrail can respond.

Third, latency is the real attack surface. Adding a synchronous LLM inference call to the critical path of every agent action — which many "AI firewall" products do — introduces a 100–2000ms blocking penalty. Under load, this becomes a denial-of-service vector against your own infrastructure.

The most verifiable containment primitive is physics-based: intercept at the syscall layer (Ring-0), where the kernel enforces the boundary between user-space intent and physical resource access. This is what the Vantio Phantom Engine does for the workloads you enroll.`,
  },
  {
    id: "02", tier: "03",
    title: "Achieving Wave Function Collapse in Agentic Workflows",
    sub: "How deterministic enforcement collapse points at the kernel boundary reduce multi-agent probability space to a single cryptographically committed outcome, eliminating governance ambiguity.",
    body: `Multi-agent systems exhibit a governance paradox: the more autonomous agents you deploy, the larger the probability space of possible system states, and the harder it becomes to demonstrate compliance with any given governance policy.

Wave Function Collapse is the process of collapsing this probability space to a single, cryptographically committed outcome at a deterministic enforcement point. In the Vantio architecture, this collapse point is the kernel boundary.

When an enrolled agent's action reaches a monitored syscall — execve, openat, or an SSL_write to a non-allowlisted host — the Phantom Engine's eBPF program makes a binary enforcement decision (TC_ACT_OK or TC_ACT_SHOT) with zero ambiguity. This decision is committed to the TrueTimeLedger with a globally consistent timestamp.

The result is an audit trail where every action of an enrolled agent has exactly one committed governance verdict — a single, verifiable collapse point — regardless of how many enrolled agents are running simultaneously or how non-deterministically they interleave. Workloads you have not enrolled are left untouched.`,
  },
  {
    id: "03", tier: "03",
    title: "The Cryptographic Anomaly Record",
    sub: "The Vantio Anomaly Record schema — a cryptographic receipt committed to a TrueTime-stamped Spanner ledger — and its direct mapping to GDPR Article 30, SOC 2 CC7.2, and SEC Cybersecurity Disclosure rules.",
    body: `The Anomaly Record is the foundational artifact of the Vantio compliance system. It is a structured record containing: a VANTIO_TRACE_ID (UUID v4), execution metadata (PID, bytes_severed, target_host, action_taken), an HMAC-SHA256 receipt over the event's trace ID, and a TrueTime commit timestamp from GCP Spanner.

The HMAC receipt is computed using the tenant's API key as the signing secret and returned in the x-vantio-signature header. This means every event is independently verifiable: a holder of the tenant key can recompute the HMAC and confirm the receipt was issued for that exact trace ID.

The payload quarantine is enforced at two layers: structurally (the ingest route whitelists only specific metadata fields — prompts and completions are architecturally excluded) and contractually (the Supabase service role key used for writes has no read access on the raw input columns).

GDPR Article 30 requires a "record of processing activities." The TrueTimeLedger satisfies this requirement natively: every agent action that touches personal data produces an immutable record with a globally consistent timestamp, a unique event ID, and a cryptographic proof of integrity.`,
  },
  {
    id: "04", tier: "02",
    title: "Eradicating Static Credentials in Autonomous Systems",
    sub: "Static API keys in autonomous agent deployments are the dominant supply-chain attack vector. Architecture for WIF/OIDC short-lived token issuance as the replacement primitive.",
    body: `Static API keys embedded in agent configurations represent the single highest-probability attack vector in autonomous AI deployments. They are long-lived, broadly scoped, frequently over-privileged, and routinely committed to version control.

The Vantio architecture addresses this at the issuance layer. The VANTIO_API_KEY issued on checkout is a random 256-bit token scoped exclusively to the tenant's anomaly_events table — it can insert but never read, update, or delete. The API key is validated against the tenants table on every ingest request before any business logic runs.

The longer-term architecture uses Workload Identity Federation (WIF) for Tier 03 enterprise deployments: the Kubernetes DaemonSet requests a short-lived OIDC token from the cluster's identity provider, exchanges it for a GCP service account credential with exactly the permissions required for the current write, and discards it after use. No long-lived credentials in the DaemonSet manifest.

For Tier 01/02 SDK users, the VANTIO_API_KEY should be stored in a secrets manager (AWS Secrets Manager, HashiCorp Vault, GCP Secret Manager) and injected at runtime via the process supervisor — never hardcoded in source files.`,
  },
  {
    id: "05", tier: "01",
    title: "Stateful Observability in Non-Deterministic Systems",
    sub: "How the Tier 01 SDK's shield() interceptor pipes execution context to the Oracle Trace Plane for Datadog-tier visualization of LangChain, CrewAI, and AutoGPT execution graphs.",
    body: `Non-deterministic systems — LLM agents, multi-agent pipelines, tool-calling chains — present a unique observability challenge: the execution graph is not known at compile time, and traditional tracing systems built on deterministic call stacks fail to capture the branching, backtracking, and parallel execution patterns of modern agentic workflows.

The Vantio SDK solves this with AsyncLocalStorage-based context propagation. The VANTIO_TRACE_ID is generated once at the entry point of a shield() call and propagated invisibly through every async hop in the call tree — tool calls, sub-agent invocations, retries, parallel tool use — without any modification to the agent's code.

Every event emitted by the SDK carries this trace ID. The Oracle UI can reconstruct the full execution graph by grouping events by trace ID and sorting by timestamp — revealing which tool calls led to which model completions, which agent instances ran in parallel, and where governance decisions were made.

This gives you Datadog-tier distributed tracing for agentic systems, with the additional property that every node in the graph has a cryptographic governance verdict attached.`,
  },
  {
    id: "06", tier: "01",
    title: "Escaping the Python Global OS Lock",
    sub: "PEP-668 and OS-level package manager restrictions create dependency isolation failure in agent deployments. Architecture for deterministic Python environment isolation.",
    body: `PEP-668 (Externally Managed Environments) introduced a class of deployment failures specific to Python-based AI agent deployments in production environments: the OS package manager marks the system Python as externally managed, preventing pip installs without explicit overrides. In containerized deployments, this interacts with base image Python versions in non-obvious ways.

The Vantio Python SDK (vantio-agent-sdk on PyPI) is designed to have zero dependencies beyond the Python standard library for its core tracing functionality. The shield() decorator and context manager require only asyncio — no aiohttp, no httpx, no requests. The optional cloud ingest path uses urllib.request from the standard library.

This means the SDK installs cleanly in managed environments (PEP-668 compliant), virtual environments (venv, conda, poetry), and containerized deployments without triggering dependency resolution conflicts.

For enterprise deployments where even pip install is restricted, the SDK can be vendored: copy vantio/ into your project directly. The entire tracing core is a single file under 200 lines.`,
  },
  {
    id: "07", tier: "02",
    title: "Application-Layer Governance: Enforcing Multi-Provider Policy",
    sub: "Tier 02 SDK-side policy enforcement across multiple AI providers. The SDK pulls a cloud-managed policy and redacts PII, caps spend, and blocks off-policy hosts locally — Vantio stores the policy and a metadata-only audit trail, never your prompts or completions.",
    body: `The Tier 02 model solves a specific deployment constraint: teams that need active AI governance but cannot — or will not — install a kernel-level enforcement agent. Enforcement runs inside the customer's own SDK/CLI. Vantio is not a network proxy and never sits in the request path.

When VANTIO_CLOUD_INGEST=true is set, the SDK fetches a cloud-managed policy from /api/v1/config and enforces it in-process: it redacts the configured PII categories from outbound requests, blocks calls to hosts outside the allow-list, and stops spend once a per-run cap is reached. Outbound AI API calls go directly to OpenAI, Anthropic, Google Vertex, AWS Bedrock, or Cohere — they are never routed through Vantio, so no prompt or completion content ever reaches our servers.

Each decision — OBSERVED, ALLOWED, REDACTED, BLOCKED_HOST, BLOCKED_SIZE, or BLOCKED_SPEND — emits a metadata-only event to the audit trail, sealed with an HMAC-SHA256 receipt. The payload quarantine guarantees only structural metadata (target host, byte counts, action, PID) is ever stored.

Because enforcement is local, there is no added network hop and no man-in-the-middle. If the control plane is unreachable, the SDK fails open — it observes only and never blocks the agent on a Vantio outage. Policy changes made in the dashboard propagate to the SDK on its next config pull, and the agent's request path is unchanged.`,
  },
];

export default function ResearchPage() {
  return (
    <main className="mx-auto max-w-4xl px-6 py-24">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Research", path: "/research" }])} />
      <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[--accent]">Research</p>
      <h1 className="mb-4 text-4xl font-bold">Engineering Dossiers.</h1>
      <p className="mb-8 max-w-2xl text-[--muted]">
        Seven research tracks documenting Vantio&apos;s technical architecture across the AI governance market — from enterprise kernel containment for F500 CISOs to developer-grade observability for open-source contributors.
      </p>

      {/* Tier legend */}
      <div className="mb-14 flex flex-wrap gap-3">
        <span className="inline-flex items-center gap-2 rounded-full border border-[--accent]/30 bg-[--accent]/5 px-3 py-1.5 text-xs font-semibold text-[--accent]">
          <span className="h-1.5 w-1.5 rounded-full bg-[--accent]" />
          Tier 01 — Developer
        </span>
        <span className="inline-flex items-center gap-2 rounded-full border border-blue-400/30 bg-blue-400/5 px-3 py-1.5 text-xs font-semibold text-blue-400">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
          Tier 02 — Pro
        </span>
        <span className="inline-flex items-center gap-2 rounded-full border border-red-400/30 bg-red-400/5 px-3 py-1.5 text-xs font-semibold text-red-400">
          <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
          Tier 03 — Enterprise
        </span>
      </div>

      <div className="space-y-8">
        {DOSSIERS.map(({ id, tier, title, sub, body }) => {
          const s = TIER_STYLE[tier] ?? TIER_STYLE["01"];
          return (
          <div key={id} className={`rounded-xl border ${s.border} ${s.bg} p-8`}>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <span className={`font-mono text-xs font-semibold ${s.badge}`}>Dossier {id}</span>
              <span className={`rounded-full border ${s.border} px-2.5 py-0.5 text-xs font-semibold ${s.badge}`}>
                {s.label}
              </span>
            </div>
            <h2 className="mb-2 text-xl font-bold">{title}</h2>
            <p className={`mb-6 text-sm font-medium ${s.badge}`}>{sub}</p>
            <div className="space-y-4 text-sm leading-relaxed text-[--muted]">
              {body.trim().split("\n\n").map((para, i) => (
                <p key={i}>{para}</p>
              ))}
            </div>
          </div>
          );
        })}
      </div>
    </main>
  );
}
