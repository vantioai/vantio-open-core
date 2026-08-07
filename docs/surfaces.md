# Vantio integration surfaces

> **Gate commercial/production:** deferred until Stripe/banking. Gate MCP dry-run may exist as POC; do not market as production enforce.

How Optics / Gate show up where agents already run — and what is earmarked for later.

## High leverage (shipping)

| Surface | Status | Location |
|---------|--------|----------|
| Optics MCP | Live | `packages/vantio-optics-mcp` · `@vantio/optics-mcp` |
| Gate MCP (dry-run) | POC — commercial deferred | `packages/vantio-gate-mcp` · `@vantio/gate-mcp` |
| Framework adapters | Shipping | [framework-integrations.md](./framework-integrations.md) + `examples/adapters/` |
| Cursor / Claude / OpenClaw hooks | Shipping | `integrations/hooks/` |
| VS Code extension (thin) | Shipping | `extensions/vantio-optics/` |

## Distribution (shipping)

| Surface | Status | Location |
|---------|--------|----------|
| GitHub Action (`vantio prove`) | Shipping | `.github/actions/vantio-prove/` |
| Docker observe wrapper | Shipping | `deploy/docker/` |
| Outbound webhooks stub | Shipping | `docs/webhooks.md` + Pro ingest pattern |
| MCP marketplaces | Live (Optics) | Registry · Cursor · mcp.so · directory |

## Deeper platform (earmarked — after)

Do **not** build these until Optics/Gate surfaces are adopted:

1. **Hosted remote MCP / Smithery URL** — multi-tenant observe API (local `~/.vantio/runs` is not enough)
2. **OpenAI / Anthropic custom GPT / tool actions** — Optics as a first-party callable tool
3. **SIEM / OpenTelemetry exporter** — metadata events → Splunk, Datadog, Elastic
4. **Browser extension** — Shadow AI discover on endpoints (secondary to agent runtime)
5. **Phantom evidence MCP** — Enterprise-only, dual-control; never free-form agent kill-switches

Track: https://github.com/vantioai/vantio-open-core/issues/3
