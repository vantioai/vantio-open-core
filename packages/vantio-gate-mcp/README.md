# @vantio/gate-mcp

**Vantio Gate MCP** — dry-run / evaluate **rules that stick** for IDEs and agent hosts.

> **Legacy/compat note:** Gate is the internal name for the Enforce function set inside
> **Vantio Phantom Engine**. This MCP package is provided for dry-run evaluation and compat
> use; Gate is not a current standalone public SKU.

This MCP can fetch policy, normalize it, and evaluate "would this call be blocked?" decisions. It **cannot** block live traffic, push unconstrained policy, or claim Phantom Engine host protection.

> Dry-run evaluate only. Live enforce = `vantio run` + Phantom Engine policy.

## Install

```bash
npx -y @vantio/gate-mcp
```

Cursor / Claude Desktop:

```json
{
  "mcpServers": {
    "vantio-gate": {
      "command": "npx",
      "args": ["-y", "@vantio/gate-mcp"],
      "env": {
        "VANTIO_API_KEY": "optional-phantom-engine-key"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
|------|---------|
| `gate_evaluate` | Dry-run host / size / spend decision |
| `gate_get_policy` | Fetch policy (needs API key) |
| `gate_residual_risk` | Enforcement-gap ledger |
| `gate_normalize_policy` | Coerce policy to canonical schema |
| `gate_explain` | Fence + rules that stick |
| `gate_upgrade_path` | Optics → Phantom Engine → Enterprise |

## Upgrade path

1. **Optics** (free) — observe only (`@vantio/optics-mcp`)
2. **Phantom Engine** ($799/node/mo) — Observe, Enforce, and Control in one purchase
3. **Enterprise** — governance add-on; talk to sales

https://vantio.ai/pricing

## License

MIT · Vantio AI, Inc.
