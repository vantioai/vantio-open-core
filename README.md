# Vantio AI: Open-Core SDK & CLI

> Zero-line agent governance. Automatic LLM observability in under 60 seconds — no code changes required.

## The Open-Core Schism

This repository is **Tier 01/02** of the Vantio architecture. It contains the open-source `@vantio/agent-sdk`, the `vantio` process supervisor CLI, and the Next.js control plane.

The proprietary **Phantom Engine** (Ring-0 eBPF enforcement, `ssl_write` uprobe, `sched_process_fork` PID inheritance) lives in a physically separate, private repository and never touches this codebase.

```
vantio-open-core  (this repo)          vantio-phantom-engine  (private)
─────────────────────────────────      ──────────────────────────────────────
Tier 1: vantio CLI + agent-sdk         Tier 3: eBPF uprobe on SSL_write
Tier 2: Managed Edge Proxy + dashboard         BTF tracepoint: sched_process_fork
User-space only, works everywhere              Pinned map: /sys/fs/bpf/vantio_trace_map
                                               Linux kernel only, requires root
```

## 60-Second Time-To-Value

### 1. Install

```bash
npm install -g @vantio/cli
```

### 2. Set your API key (Tier 2 — from app.vantio.ai/success)

```bash
export VANTIO_API_KEY=vantio_xxxxxxxxxxxx
export VANTIO_INGEST_URL=https://app.vantio.ai
```

### 3. Run your agent — zero code changes

```bash
vantio run node agent.js
vantio run --audit tsx agent.ts
```

The CLI auto-injects the `global.fetch` interceptor into the Node.js runtime via `--require`. Every outbound call to a known LLM API (`api.openai.com`, `api.anthropic.com`, etc.) is automatically captured and routed to your dashboard. **Your application code changes nothing.**

For Python, Ruby, or other runtimes, `vantio run` spawns the process normally — no errors, no panics. Auto-interception is Node.js only at this stage.

## Upgrade to the SDK (optional)

For teams that want explicit trace correlation across async hops:

```ts
import { withVantio, reportAnomaly } from "@vantio/agent-sdk";

await withVantio(async () => {
  await runMyLLMAgent();
  // Manual reporting for non-HTTP anomalies:
  await reportAnomaly({ target_host: "api.openai.com", action_taken: "POLICY_VIOLATION" });
});
```

Set `VANTIO_CLOUD_INGEST=true` alongside `VANTIO_API_KEY` to enable cloud routing.

## Monorepo Structure

```
apps/
  web/                  Next.js 15 control plane (App Router)
    api/v1/ingest/      Edge route — telemetry ingestion (rate limited: 100/min/key)
    api/v1/export/      CSV export of anomaly ledger
    api/webhooks/stripe/ Stripe checkout.session.completed → tenant PRO
    api/stripe/         Checkout session creation
    dashboard/          SMB live anomaly event dashboard (auth-gated)
    login/              Supabase magic link auth
    pricing/            Three-tier pricing page
    success/            Post-payment onboarding
    trust/              Compliance & governance
    auth/enterprise/    Enterprise SAML/SSO gateway UI

packages/
  vantio-agent-sdk/     withVantio() + reportAnomaly() — AsyncLocalStorage SDK
  vantio-cli/           vantio run — process supervisor + auto-interceptor
  edge-proxy/           Spanner TrueTime Ledger mutation helper
```

## Slack Alerting (Tier 2 — Zero Code)

Wire Supabase → n8n → Slack using a Database Webhook (no code required):

1. Supabase Dashboard → Database → Webhooks → Create
2. Table: `anomaly_events`, Event: `INSERT`
3. URL: your n8n webhook endpoint
4. n8n workflow: parse JSON body → Slack message to `#devops-alerts`

## Roadmap (Post-Launch / Enterprise GA)

- Remote config endpoint for zero-touch tier upgrades
- Policy rules engine (dashboard-driven, no code push)
- RBAC for team access
- Python / Ruby interceptor support
- GCP Spanner TrueTime Ledger (Tier 3 GA)

## Supply Chain

Every push to `main` triggers SLSA Level 3 Sigstore provenance attestation.

[![SLSA L3 Provenance](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)

## License

`@vantio/agent-sdk` and `@vantio/cli` — MIT  
`apps/web` (control plane) — Proprietary © 2026 Vantio AI, Inc.
