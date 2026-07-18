# Vantio Optics

Observe-only **Sight Loop** commands for VS Code. Thin wrappers over the Vantio CLI — prove what Optics saw, discover local LLM hosts, and surface the residual upgrade path.

**Blind by design:** this extension does not block, redact, or enforce policy.

## Commands

| Command | What it does |
|---------|----------------|
| **Vantio: Export Optics proof** | Runs `vantio prove --format=md` |
| **Vantio: Discover local LLM hosts** | Runs `vantio discover --local` |
| **Vantio: Show upgrade path** | Residual ladder beyond observe (honest cue, not enforce) |

## Requirements

```bash
npm install -g @vantio/cli
```

Optics must have local run logs under `~/.vantio/runs` (from `vantio run`, SDK `@shield`, or equivalent).

## Install

- **Marketplace:** search `Vantio Optics` (`vantioai.vantio-optics`) once published
- **VSIX:** `code --install-extension vantio-optics-0.1.0.vsix`

For Cursor agent hosts, prefer the [Cursor / Open plugin](https://github.com/vantioai/vantio-optics-cursor-plugin) and `@vantio/optics-mcp`.

## Links

- Platform: https://vantio.ai/optics
- Pricing / upgrade: https://vantio.ai/pricing
- Source: https://github.com/vantioai/vantio-open-core/tree/main/extensions/vantio-optics

MIT · Vantio AI, Inc.
