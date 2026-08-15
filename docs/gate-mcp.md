# Vantio Gate MCP

Part of **Vantio Gate** · **Rules that stick** (dry-run evaluate via Model Context Protocol).

Package: [`@vantio/gate-mcp`](../packages/vantio-gate-mcp/)

## Fence

> Dry-run evaluate only. Live enforce is `vantio run` plus Gate policy — not this MCP.

- Evaluates host / size / spend decisions
- Fetches Gate policy + residual-risk (with API key)
- **Never** blocks live traffic from inside the MCP
- **Never** pushes unconstrained policy to production
- **Never** claims Phantom Engine host protection

Live enforce remains `vantio run` + Gate. Phantom Engine remains a separate Linux-host purchase.

## Quick start

```bash
npx -y @vantio/gate-mcp
```

See [surfaces.md](./surfaces.md) for the full integration map.
