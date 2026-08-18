# @vantio/gate-mcp

**Vantio Gate** MCP — dry-run / evaluate **rules that stick** for IDEs and agent hosts (internal workflow id: Policy Latch).

This MCP can fetch policy, normalize it, and evaluate “would this call be blocked?” decisions. It **cannot** block live traffic, push unconstrained policy, or expose Control.

> Dry-run evaluate only. Live enforce = `vantio run` + Pro policy.

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
        "VANTIO_API_KEY": "optional-pro-key"
      }
    }
  }
}
```

## Tools

| Tool | Purpose |
|------|---------|
| `gate_evaluate` | Dry-run host / size / spend decision |
| `gate_get_policy` | Fetch Pro policy (needs API key) |
| `gate_residual_risk` | Enforcement-gap ledger (Pro) |
| `gate_normalize_policy` | Coerce policy to canonical schema |
| `gate_explain` | Fence + rules that stick |
| `gate_upgrade_path` | Optics → Gate → Phantom Engine |

## Upgrade path

1. **Optics** — see (`@vantio/optics-mcp`)  
2. **Gate** — this MCP (evaluate) + Pro runtime (enforce)  
3. **Phantom Engine** — premium Control  

https://vantio.ai/pricing

## License

MIT · Vantio AI, Inc.
