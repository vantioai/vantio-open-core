# Agent host hooks — Vantio Optics

Opt-in wrappers so agent hosts start processes under **Sight Loop** observe.

| Host | File |
|------|------|
| Cursor | `cursor-hooks.json` → merge into `.cursor/hooks.json` |
| Claude Code | `claude-code-settings.example.json` |
| OpenClaw | `openclaw-plugin.example.md` |
| Helper | `lib/maybe-vantio-run.mjs` |

```bash
export VANTIO_HOOKS=1
npm install -g @vantio/cli
```

Fence: observe only. Pair with `@vantio/optics-mcp` / `@vantio/gate-mcp` in the IDE.
