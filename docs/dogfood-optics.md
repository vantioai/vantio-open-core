# Dogfood Optics (local)

Short loop to prove **Vantio Optics** on your machine — observe only, no Gate/billing required.

## 1. Wrap — `vantio run`

```bash
npm install -g @vantio/cli
vantio run node agent.js
```

No API key. Free Observe writes metadata to `~/.vantio/runs/` (never prompts/completions).

## 2. Export — `vantio prove`

```bash
vantio prove                  # HTML proof from the latest run
vantio prove --format md      # Markdown
vantio discover --local       # hosts / history from local logs
```

## 3. Agent host — Optics MCP

```bash
npx -y @vantio/optics-mcp
```

Cursor / Claude Desktop:

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

Read-only tools: list/inspect runs, prove, discover local, explain, upgrade path.  
Details: [optics-mcp.md](./optics-mcp.md) · full workflow: [sight-loop.md](./sight-loop.md).

## Fence

Optics **observes**. It does not block, redact, or latch policy.  
**Gate commercial/production** (Stripe/banking) is deferred — see [surfaces.md](./surfaces.md).
