import type { Metadata } from "next";
import { buildMetadata, breadcrumbJsonLd } from "@/lib/seo";
import { JsonLd } from "@/components/json-ld";
import { CodeBlock } from "@/components/code-block";

export const metadata: Metadata = buildMetadata({
  title: "Developers",
  description: "Ship AI governance in two lines of code. Node.js and Python SDK with zero refactoring.",
  path: "/developers",
});

const NODE_SHIELD = `import { shield, getCurrentTraceId } from "@vantio/agent-sdk";

// shield() wraps any async agent call.
// Generates a VANTIO_TRACE_ID and propagates it via AsyncLocalStorage.
const result = await shield(async () => {
  return await runMyLLMAgent();
});`;

const NODE_REPORT = `import { shield, reportAnomaly } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyAgent();

  // Report a detected anomaly to the Oracle ledger.
  // Zero linguistic content — execution metadata only.
  await reportAnomaly({
    target_host:   "api.openai.com",
    bytes_severed: 14382,
    action_taken:  "POLICY_VIOLATION",
  });
});`;

const PY_SHIELD = `from vantio import shield, report_anomaly

# Decorator form — zero changes to your agent logic.
@shield
async def run_agent():
    result = await call_openai(prompt)
    return result

# Or as a context manager:
async with shield() as trace:
    print(f"Trace ID: {trace.trace_id}")
    result = await run_agent()`;

const PY_REPORT = `from vantio import shield, report_anomaly

async with shield():
    await run_agent()
    
    # Report anomaly — fires async, never blocks your agent.
    await report_anomaly(
        target_host="api.openai.com",
        bytes_severed=14382,
        action_taken="POLICY_VIOLATION",
    )`;

const CLI_USAGE = `# Zero code changes — wraps any process
vantio run node agent.js
vantio run python agent.py
vantio run --audit tsx agent.ts   # VANTIO_AUDIT_MODE=1
vantio run --summary node agent.js  # prints run summary on exit`;

const FRAMEWORKS = [
  "LangChain", "AutoGen", "CrewAI", "AWS Bedrock Agents",
  "OpenAI API", "Anthropic API", "Google Vertex", "LlamaIndex",
  "Haystack", "Semantic Kernel",
];

export default function DevelopersPage() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-24">
      <JsonLd data={breadcrumbJsonLd([{ name: "Home", path: "/" }, { name: "Developers", path: "/developers" }])} />
      <span className="mb-4 inline-flex items-center gap-2 rounded-full border border-[var(--accent)]/30 bg-[var(--accent)]/5 px-4 py-1.5 text-xs font-semibold text-[var(--accent)]">
        Tier 01 — Developer · Open-Core · Free
      </span>
      <h1 className="mb-4 text-4xl font-bold">
        Ship AI Governance in<br />
        <span className="text-[var(--accent)]">Two Lines of Code.</span>
      </h1>
      <p className="mb-6 max-w-2xl text-lg text-[var(--muted)]">
        <span className="font-semibold text-[var(--foreground)]">Vantio Open Core</span> is the free,
        open-source SDK + CLI that gives your AI agents governance in two lines of code. Install via
        npm or pip, wrap a call with <code className="rounded bg-[var(--surface)] px-1 text-[var(--accent)]">shield()</code> or
        invoke any agent with <code className="rounded bg-[var(--surface)] px-1 text-[var(--accent)]">vantio run</code> —
        zero code changes required. 10,000 events/month, free, with every event HMAC-signed and
        cryptographically receipted. SDK, CLI, and Python SDK are all at <code className="rounded bg-[var(--surface)] px-1 text-[var(--accent)]">v0.2.0</code>.
      </p>
      <div className="mb-16 flex gap-3">
        <a href="/dashboard" className="rounded-md bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-black hover:bg-[var(--accent-dim)]">
          Get API Key — Free
        </a>
        <a href="https://github.com/vantioai/vantio-open-core" target="_blank" rel="noopener noreferrer"
          className="rounded-md border border-[var(--border)] px-5 py-2.5 text-sm font-medium text-[var(--muted)] hover:border-[var(--foreground)] hover:text-[var(--foreground)]">
          View on GitHub
        </a>
      </div>

      {/* SDK tabs */}
      <div className="mb-20 grid gap-12 md:grid-cols-2">
        {/* Node.js */}
        <div>
          <div className="mb-4 flex items-center gap-2">
            <span className="rounded bg-green-500/20 px-2 py-0.5 text-xs font-bold text-green-400">npm</span>
            <span className="text-sm font-semibold">TypeScript / Node.js</span>
          </div>
          <div className="space-y-5">
            <CodeBlock code="npm install @vantio/agent-sdk" accent />
            <CodeBlock label="shield() — basic wrapping" code={NODE_SHIELD} />
            <CodeBlock label="reportAnomaly() — metadata telemetry" code={NODE_REPORT} />
          </div>
        </div>

        {/* Python */}
        <div>
          <div className="mb-4 flex items-center gap-2">
            <span className="rounded bg-yellow-500/20 px-2 py-0.5 text-xs font-bold text-yellow-400">PyPI</span>
            <span className="text-sm font-semibold">Python</span>
          </div>
          <div className="space-y-5">
            <CodeBlock code="pip install vantio-agent-sdk" accent />
            <CodeBlock label="@shield — decorator / context manager" code={PY_SHIELD} />
            <CodeBlock label="report_anomaly() — metadata telemetry" code={PY_REPORT} />
          </div>
        </div>
      </div>

      {/* CLI */}
      <div className="mb-20 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-8">
        <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-[var(--accent)]">Zero-Line Integration</div>
        <h2 className="mb-2 text-xl font-bold">vantio run — Any Process, Any Stack</h2>
        <p className="mb-6 text-sm text-[var(--muted)]">
          No code changes at all. The CLI injects the interceptor at runtime via <code className="text-[var(--accent)]">NODE_OPTIONS</code> (which carries <code className="text-[var(--accent)]">--require</code>),
          patching <code className="text-[var(--accent)]">globalThis.fetch</code> before your agent starts — uniformly across <code className="text-[var(--accent)]">node</code>, <code className="text-[var(--accent)]">npx</code>, <code className="text-[var(--accent)]">tsx</code>, and <code className="text-[var(--accent)]">ts-node</code>.
          Python, Ruby, and other runtimes are spawned normally without injection; use the Python SDK for those.
        </p>
        <CodeBlock code={CLI_USAGE} className="bg-black/40" />
      </div>

      {/* What the SDK does */}
      <div className="mb-20">
        <h2 className="mb-8 text-xl font-bold">What the SDK Does</h2>
        <div className="grid gap-4 md:grid-cols-2">
          {[
            { title: "HMAC-Signed Telemetry", body: "Every event is HMAC-SHA256 signed with your API key before transmission. Events are cryptographically receipted in the Oracle ledger — independently verifiable without trusting the ledger itself." },
            { title: "AsyncLocalStorage Propagation", body: "The VANTIO_TRACE_ID propagates through the full async call-tree via AsyncLocalStorage — no monkey-patching, no global state, no AST modifications." },
            { title: "Payload Quarantine", body: "Zero linguistic content ever reaches the ledger. The ingest route structurally enforces a whitelist of fields (bytes_severed, pid, target_host, action_taken) — prompts and completions are architecturally excluded." },
            { title: "Non-Blocking Telemetry", body: "Telemetry emission is fully async — the shield() interceptor adds microsecond-scale overhead on the synchronous critical path. Anonymous usage telemetry is opt-out (VANTIO_TELEMETRY_DISABLED=1 or DO_NOT_TRACK=1) and metadata only. Production-safe from day one." },
            { title: "Multi-Framework", body: "Works with LangChain, AutoGen, CrewAI, AWS Bedrock Agents, and any raw OpenAI/Anthropic API call. Zero refactoring required." },
            { title: "SLSA Level 3 Provenance", body: "Our build pipeline emits SLSA Level 3 provenance: npm and CLI build artifacts are attested with GitHub's build-provenance action and recorded keylessly in the Sigstore/Rekor transparency log." },
          ].map(({ title, body }) => (
            <div key={title} className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-5">
              <h3 className="mb-2 text-sm font-semibold text-[var(--accent)]">→ {title}</h3>
              <p className="text-xs text-[var(--muted)]">{body}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Supported frameworks */}
      <div className="mb-12">
        <h2 className="mb-4 text-xl font-bold">Supported Frameworks</h2>
        <div className="flex flex-wrap gap-2">
          {FRAMEWORKS.map((f) => (
            <span key={f} className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs text-[var(--muted)]">{f}</span>
          ))}
        </div>
      </div>

      <div className="rounded-lg border border-[var(--accent)]/20 bg-[var(--accent)]/5 p-5 text-xs text-[var(--muted)]">
        <strong className="text-[var(--foreground)]">Ring-3 boundary note:</strong>{" "}
        Ring-3 application-layer visibility does not equal Ring-0 OS-level enforcement. The Developer SDK operates entirely in user-space.
        It intercepts application-layer function calls and emits telemetry — it does not enforce at the kernel level.
        For Ring-0 kernel enforcement, see the{" "}
        <a href="/enterprise" className="text-red-400 underline">Enterprise tier</a>.
        For managed SDK-side enforcement — PII redaction, spend caps, and host blocking driven by a cloud policy — see the{" "}
        <a href="/pro" className="text-blue-400 underline">Pro tier</a>.
      </div>
    </main>
  );
}
