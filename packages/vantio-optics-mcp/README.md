# @vantio/optics-mcp

**Vantio Optics** MCP server — read-only **Observe** / **Sight Loop** for AI agents and IDEs.

This MCP lets hosts list local run logs, inspect traffic metadata, export proofs, and discover hosts. It **cannot** enforce policy. For rules that stick, upgrade to **Vantio Gate**. For premium host lock-down when paths miss the app layer, upgrade to **Vantio Phantom Engine**.

> No prompts or completions. Observe only.

## Install

```bash
# from vantio-open-core monorepo
pnpm install --filter @vantio/optics-mcp

# or globally (when published)
npm install -g @vantio/optics-mcp
```

Generate Optics traffic first (optional but recommended):

```bash
npm install -g @vantio/cli
vantio run node your-agent.js
```

## Cursor / Claude Desktop config

```json
{
  "mcpServers": {
    "vantio-optics": {
      "command": "npx",
      "args": ["-y", "@vantio/optics-mcp"]
    }
  }
}
```

Local checkout:

```json
{
  "mcpServers": {
    "vantio-optics": {
      "command": "node",
      "args": [
        "/absolute/path/to/vantio-open-core/packages/vantio-optics-mcp/bin/vantio-optics-mcp.js"
      ]
    }
  }
}
```

## Tools (observe only)

| Tool | Purpose |
|------|---------|
| `optics_list_runs` | List `~/.vantio/runs` |
| `optics_get_run` | Load one run (metadata only) |
| `optics_prove` | Markdown Sight Loop proof |
| `optics_discover_local` | Aggregate hosts from local logs |
| `optics_explain` | Optics privacy + fence |
| `optics_upgrade_path` | Ladder → Gate → Phantom Engine |

## Upgrade path

1. **Optics** (this MCP) — see  
2. **Gate** (Pro) — rules that stick / enforce  
3. **Phantom Engine** (Enterprise) — Rogue Reconciliation / Absolute Control  

https://vantio.ai/pricing

## License

MIT · Vantio AI, Inc.
