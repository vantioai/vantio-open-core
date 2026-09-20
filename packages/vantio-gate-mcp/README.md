# @vantio/gate-mcp

**@vantio/gate-mcp** is a legacy compatibility package for Phantom Engine's supported application-path enforcement functions. Gate is not a separate Vantio product or subscription.

> Dry-run evaluate only. Live enforce = `vantio run` + Phantom Engine policy.

This MCP can fetch policy, normalize it, and evaluate "would this call be blocked?" decisions. It **cannot** block live traffic, push unconstrained policy, or claim Phantom Engine host protection.

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

> The `vantio-gate` host key is the legacy MCP registry identifier and is preserved for compatibility.

## Tools

| Tool | Purpose |
|------|---------|
| `gate_evaluate` | Dry-run host / size / spend decision |
| `gate_get_policy` | Fetch policy (needs API key) |
| `gate_residual_risk` | Enforcement-gap ledger |
| `gate_normalize_policy` | Coerce policy to canonical schema |
| `gate_explain` | Fence + rules that stick |
| `gate_upgrade_path` | Optics → Phantom Engine → Enterprise |

> `gate_explain` JSON: `phantom` is the current product URL field (`https://vantio.ai/phantom`). The `gate` key is a **legacy compatibility alias** for that same URL — not a product SKU.

## Upgrade path

1. **Optics** (free) — observe only (`@vantio/optics-mcp`)
2. **Phantom Engine** ($799/node/mo) — Observe, Enforce, and Control in one purchase
3. **Enterprise** — governance add-on; talk to sales

https://vantio.ai/phantom · https://vantio.ai/pricing

## License

MIT · Vantio AI, Inc.

## Changelog

### 0.1.1
- Metadata/branding correction: `gate_explain` response, `package.json`, `server.json` description all consistently frame this as a Phantom Engine compatibility layer, not a standalone Gate SKU.
- Restored `gate_explain.gate` as a **legacy compatibility alias** — `gate: "https://vantio.ai/phantom"` is retained alongside `phantom: "https://vantio.ai/phantom"` for private MCP consumers that read `response.gate`. Gate is not a product SKU.

### 0.1.0
- Initial release: dry-run evaluate, policy fetch, normalize, and explain tools for Phantom Engine application-path enforcement.
