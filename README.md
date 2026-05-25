# Vantio AI: Open-Core SDK & CLI

> Zero-line AI agent governance. Automatic LLM observability in 60 seconds — no code changes required.

## The Open-Core Schism

This repository is **Tier 01 and Tier 02** of the Vantio architecture. It contains the open-source `@vantio/agent-sdk`, the `vantio` process supervisor CLI, and the Next.js control plane.

The proprietary **Phantom Engine** (Ring-0 eBPF enforcement, `ssl_write` uprobe, `sched_process_fork` PID inheritance) lives in a physically separate, private repository and never touches this codebase.

```
vantio-open-core  (this repo)          vantio-phantom-engine  (private)
─────────────────────────────────      ──────────────────────────────────────
Tier 01: vantio CLI + agent-sdk        Tier 03: eBPF uprobe on SSL_write
Tier 02: Managed Edge Proxy            BTF tracepoint: sched_process_fork
         + dashboard + Supabase        Pinned map: /sys/fs/bpf/vantio_trace_map
User-space only, works everywhere      Linux kernel only, requires root
```

## 60-Second Time-To-Value

### 1. Install the CLI

```bash
npm install -g @vantio/cli       # Node.js agents
pip install vantio-agent-sdk     # Python agents
```

### 2. Set your API key (Tier 02 — from vantio.ai/success)

```bash
export VANTIO_API_KEY=vantio_xxxxxxxxxxxx
export VANTIO_INGEST_URL=https://vantio.ai
export VANTIO_CLOUD_INGEST=true
```

### 3. Run your agent — zero code changes

```bash
vantio run node agent.js          # auto-intercepts all outbound LLM calls
vantio run python agent.py        # Python agents
vantio run --audit tsx agent.ts   # VANTIO_AUDIT_MODE=1
vantio run --summary node agent.js  # prints run summary on exit
```

The CLI auto-injects the `global.fetch` interceptor via Node.js `--require`. Every outbound call to a known LLM API is automatically captured. **Your application code doesn't change.**

## SDK Integration (optional — for explicit trace correlation)

### Node.js / TypeScript

```ts
import { shield, reportAnomaly } from "@vantio/agent-sdk";

// shield() is the canonical API — withVantio() is an alias
await shield(async () => {
  await runMyLLMAgent();

  await reportAnomaly({
    target_host:   "api.openai.com",
    action_taken:  "POLICY_VIOLATION",
    bytes_severed: 14382,
  });
});
```

### Python

```python
from vantio import shield, report_anomaly

@shield
async def run_agent():
    result = await call_openai(prompt)
    return result

# Or as a context manager:
async with shield() as trace:
    await run_agent()
    await report_anomaly(
        target_host="api.openai.com",
        action_taken="POLICY_VIOLATION",
    )
```

## Monorepo Structure

```
apps/
  web/                    Next.js 15 control plane (App Router)
    /                     Marketing homepage
    /pricing              Three-tier pricing page (Stripe checkout)
    /developers           SDK docs — Node.js + Python
    /architecture         Technical architecture deep dive
    /research             7 Engineering Dossiers (Tier 01/02/03)
    /enterprise           Enterprise landing page
    /pro-smb              PRO/SMB landing page
    /trust                Trust & compliance
    /login                Supabase magic link auth
    /dashboard            SMB live anomaly event dashboard (auth-gated)
    /success              Post-payment onboarding + API key
    /privacy              Privacy policy
    /terms                Terms of service
    api/v1/ingest/        Edge route — telemetry ingestion (100 req/min/key)
    api/v1/export/        CSV export of anomaly ledger
    api/stripe/           Checkout session + Customer Portal
    api/webhooks/stripe/  Stripe lifecycle: provision, downgrade, cancel
    api/webhooks/supabase/ Supabase INSERT → Slack Block Kit alert
    api/contact/          Enterprise lead capture → Supabase + Slack

  cli/                    TypeScript CLI (Windows WSL interop bridge)

packages/
  vantio-agent-sdk/       shield() + withVantio() + reportAnomaly() — Node.js SDK
  vantio-agent-sdk-py/    @shield + report_anomaly() — Python SDK (PyPI)
  vantio-cli/             vantio run — process supervisor + auto-interceptor
  edge-proxy/             Spanner TrueTime Ledger mutation helper
```

## Slack Alerting (Tier 02 — built-in)

Vantio ships a direct Slack integration via Supabase Database Webhooks:

1. Create a Slack app → Incoming Webhooks → copy URL
2. Add `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...` to Vercel
3. Supabase → Database → Webhooks → Create → table: `anomaly_events`, event: `INSERT`, URL: `https://vantio.ai/api/webhooks/supabase/anomaly`, header: `Authorization: Bearer <SUPABASE_WEBHOOK_SECRET>`

Every anomaly fires a rich Slack Block Kit message — tenant, target host, bytes blocked, trace ID, and a link to the dashboard.

## Environment Variables

See `.env.example` for the full list. Required for production:

```
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
STRIPE_SMB_PRICE_ID
UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN
NEXT_PUBLIC_APP_URL
```

## Supply Chain

Every push to `main` triggers SLSA Level 3 Sigstore provenance attestation and automatic npm publish of `@vantio/agent-sdk` and `@vantio/cli`.

[![SLSA L3 Provenance](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)

## Post-Launch Roadmap

- Remote config endpoint for zero-touch tier upgrades
- Policy rules engine (dashboard-driven, no code push)
- RBAC for team access (10-seat dashboard)
- Ruby / Go interceptor support
- GCP Spanner live write from Tier 02 Managed Edge Proxy

## License

`@vantio/agent-sdk`, `@vantio/agent-sdk-py`, and `@vantio/cli` — **MIT**
`apps/web` (control plane) — Proprietary © 2026 Vantio AI, Inc.
