# Vantio Gate MCP

> **Legacy/compat note:** Gate is the internal name for the Enforce function set inside
> **Vantio Phantom Engine**. This MCP package is provided for dry-run evaluation and compat use;
> Gate is not a current standalone public SKU. See [PRODUCT_LINEUP.md](./PRODUCT_LINEUP.md).

Part of the open-core repo · **Rules that stick** (dry-run evaluate via Model Context Protocol).

Package: [`@vantio/gate-mcp`](../packages/vantio-gate-mcp/)

## Fence

> Dry-run evaluate only. Live enforce is `vantio run` plus Phantom Engine policy — not this MCP.

- Evaluates host / size / spend decisions
- Fetches policy + residual-risk (with API key)
- **Never** blocks live traffic from inside the MCP
- **Never** pushes unconstrained policy to production
- **Never** claims Phantom Engine host protection

Live enforce: `vantio run` + Phantom Engine policy. Phantom Engine is the Linux-host purchase.

## Quick start

```bash
npx -y @vantio/gate-mcp
```

See [surfaces.md](./surfaces.md) for the full integration map.
