# @vantio/gate-mcp

**Vantio Gate** MCP — **Policy Latch** dry-run / evaluate for IDEs and agent hosts.

This MCP can fetch policy, normalize it, and evaluate “would this call be blocked?” decisions. It **cannot** block live traffic, push unconstrained policy, or expose Absolute Control.

> Fence: dry-run evaluate only. Live latch = `vantio run` + Pro policy.

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
| `gate_explain` | Fence + Policy Latch |
| `gate_upgrade_path` | Optics → Gate → Phantom Engine |

## Upgrade path

1. **Optics** — see (`@vantio/optics-mcp`)  
2. **Gate** — this MCP (evaluate) + Pro runtime (latch)  
3. **Phantom Engine** — Absolute Control  

https://vantio.ai/pricing

## License

MIT · Vantio AI, Inc.
