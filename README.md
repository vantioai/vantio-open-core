# Vantio AI: Open-Core SDK & CLI

> Kernel-enforced AI governance. Zero-line terminal visibility into your autonomous agents in under 60 seconds.

## The Open-Core Schism

This repository is **Tier 01** of the Vantio architecture — the public developer wedge. It contains the open-source `@vantio/agent-sdk`, the `vantio` process supervisor CLI, and the Next.js control plane.

The proprietary **Phantom Engine** (Ring-0 eBPF enforcement, `uprobe` TLS interception, `sched_process_fork` context propagation) lives in a physically separate, private repository and never touches this codebase. This is a hard architectural guarantee, not a convention.

```
vantio-open-core  (this repo)     vantio-phantom-engine  (private)
─────────────────────────────     ──────────────────────────────────
Ring-3 user-space only            Ring-0 kernel boundary
@vantio/agent-sdk (MIT)           eBPF uprobe: SSL_write
vantio CLI process supervisor     BTF tracepoint: sched_process_fork
Next.js control plane             Pinned map: /sys/fs/bpf/vantio_trace_map
Supabase tenant ledger            GCP Spanner TrueTime WORM ledger
```

## 60-Second Time-To-Value (TTV)

### 1. Install

```bash
pnpm install
```

### 2. Start the local control plane

```bash
pnpm --filter web dev
```

### 3. Wrap your agent

```ts
import { withVantio } from "@vantio/agent-sdk";

const result = await withVantio(async () => {
  return await runMyLLMAgent();
});
```

### 4. Supervise a process

```bash
vantio run node agent.js
vantio run --audit python agent.py   # VANTIO_AUDIT_MODE=1
```

The `--audit` flag injects `VANTIO_AUDIT_MODE=1` into the child process. When the Phantom Engine is active, audit mode severs the payload at the kernel boundary and spoofs an HTTP 200 back to the agent — zero application crashes, zero prompt leakage.

## Upgrade to Tier 2 (SMB / PRO)

Set `VANTIO_CLOUD_INGEST=true` to halt local writes and route telemetry to the Vantio Managed Edge Proxy (GCP Spanner):

```bash
VANTIO_CLOUD_INGEST=true vantio run node agent.js
```

The `/api/v1/ingest` edge route authenticates via `x-vantio-identity`, validates the payload, and persists anomaly events to Supabase — visible instantly in your `/dashboard`.

## Monorepo Structure

```
apps/
  web/                  Next.js 15 control plane (App Router)
    api/v1/ingest/      Edge route — telemetry ingestion to Supabase
    api/webhooks/stripe/ Stripe checkout.session.completed → tenant PRO
    dashboard/          SMB live anomaly event dashboard
    pricing/            Three-tier pricing page
    trust/              Compliance & governance (SOC 2, SLSA L3)
    auth/enterprise/    Enterprise SAML/SSO gateway UI
  cli/                  TypeScript CLI (WSL interop bridge)

packages/
  vantio-agent-sdk/     withVantio() — AsyncLocalStorage trace context
  vantio-cli/           vantio run — process supervisor (Node.js, MIT)
  edge-proxy/           Spanner TrueTime Ledger mutation helper
```

## Supply Chain

Every push to `main` triggers the SLSA Level 3 Sigstore provenance workflow. A cryptographically signed attestation is written to Rekor's tamper-evident transparency log, binding the GitHub OIDC runner identity to the artifact digest.

[![SLSA L3 Provenance](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)

## License

`@vantio/agent-sdk` and `@vantio/cli` are MIT licensed.  
The Next.js control plane (`apps/web`) is proprietary — © 2026 Vantio AI, Inc.
