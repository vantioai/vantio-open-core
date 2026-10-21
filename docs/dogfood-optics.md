# Dogfood Optics (local)

Short loop to prove **Vantio Optics** on your machine — observe only, no API key or billing required.

**Live product page:** https://vantio.ai/optics  
**Phantom Box forever soak / suite status:** sandbox [`docs/BUILD_STATUS.md`](../../docs/BUILD_STATUS.md) · [`docs/MULTI_TIER_SOAK.md`](../../docs/MULTI_TIER_SOAK.md)

## 1. Wrap — `vantio run`

```bash
npm install -g @vantio/cli
pip install vantio-agent-sdk
vantio run node agent.js
vantio run python3 agent.py
```

If `npm install -g` fails with `EACCES`, the global prefix is not writable. Use `npm install -g @vantio/cli --prefix "$HOME/.local"` and add `$HOME/.local/bin` to `PATH`. Use `vantio run python agent.py` when the `python` command exists. The pip install is required before a Python wrap intercepts.

No API key. A Node run writes metadata to `~/.vantio/runs/` even when it made no LLM call, and prints a summary only when a supported call was recorded. A Python run writes a file there only when the SDK recorded a supported call. `vantio run pnpm` and `vantio run bash` do not write a run log. Prompts and completions are never stored. A tool that does not expand `~` needs `$HOME/.vantio/runs`.

## 2. Export & inspect

```bash
vantio prove                  # HTML proof from the latest run
vantio prove --format md      # Markdown
vantio search openai          # search local run logs
vantio tail                   # latest calls from the most recent run
vantio diff <run-a> <run-b>   # compare two runs
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
Enforce and Control belong to **Phantom Engine** — see [surfaces.md](./surfaces.md) and [observe-only.md](./observe-only.md).
