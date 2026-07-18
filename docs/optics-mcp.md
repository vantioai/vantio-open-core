# Vantio Optics MCP

Part of **Vantio Optics** · **Sight Loop** (observe / explain via Model Context Protocol).

Package: [`@vantio/optics-mcp`](../packages/vantio-optics-mcp/)

## What it is

A **read-only** MCP server so IDEs and agent hosts can:

- List and inspect local Optics run logs (`~/.vantio/runs`)
- Export Markdown proofs (no prompts/completions)
- Discover LLM hosts from local logs
- Explain Optics and the upgrade ladder to Gate / Phantom Engine

## What it is not

- Not Vantio Gate — cannot block, redact, or latch policy  
- Not Phantom Engine — no Absolute Control / bypass tools  
- Not a content store — blind by design  

Agents that outgrow observe call `optics_upgrade_path` and move to Pro / Enterprise.

## Quick start

```bash
cd packages/vantio-optics-mcp
pnpm install
pnpm test
node bin/vantio-optics-mcp.js   # stdio MCP
```

Or: `npx -y @vantio/optics-mcp` (when published).

## Cursor / Claude Desktop

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

Local checkout — point `command` at `node` and `args` at  
`…/packages/vantio-optics-mcp/bin/vantio-optics-mcp.js`.

## Tools

| Tool | Purpose |
|------|---------|
| `optics_list_runs` | List `~/.vantio/runs` |
| `optics_get_run` | One run (metadata only) |
| `optics_prove` | Markdown Sight Loop proof |
| `optics_discover_local` | Hosts from local logs |
| `optics_explain` | Optics privacy + fence |
| `optics_upgrade_path` | Ladder → Gate → Phantom Engine |

Full package notes: [packages/vantio-optics-mcp/README.md](../packages/vantio-optics-mcp/README.md).
