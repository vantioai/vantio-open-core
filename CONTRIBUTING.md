# Vantio AI — Contributing

## What's in this repo

Three open-core packages:

- `packages/vantio-cli` — CLI runner (`@vantio/cli`) — end users install with `npm install -g @vantio/cli`
- `packages/vantio-agent-sdk` — Node.js agent SDK (`@vantio/agent-sdk`)
- `packages/vantio-agent-sdk-py` — Python agent SDK (`vantio-agent-sdk`)

## Development

```bash
# Install dependencies (pnpm only — see Dependency Governance below)
pnpm install

# Build all packages
pnpm build

# Run CLI directly from source
node packages/vantio-cli/bin/vantio.js

# Type-check the Node SDK
cd packages/vantio-agent-sdk && pnpm exec tsc --noEmit
```

## Engineering Directives

**Type Safety**
The `any` keyword is banned across the entire TypeScript codebase. Use `unknown` with strict type guards. PRs containing `any` will not be merged.

**Payload Quarantine**
No raw user prompts, LLM responses, or PII may be passed to the SDK telemetry payload. Strip all linguistic content at the API boundary before ingestion.

**Dependency Governance**
`pnpm` is the only authorized package manager. `npm install` and `yarn` are banned to prevent phantom dependency vectors. Do not commit `package-lock.json` or `yarn.lock`.

## Architectural Boundaries

**This repository is strictly Ring-3 user-space.** Do not submit PRs that introduce:

- eBPF programs, kernel probes, or any Ring-0 logic
- References to `/sys/fs/bpf/`, `bpf_*` helpers, or `aya-ebpf`
- Imports from or dependencies on the proprietary `vantio-phantom-engine` repository

Violations are automatically rejected by CI.

## What belongs here

| ✅ In scope | ❌ Out of scope |
|---|---|
| `@vantio/agent-sdk` improvements | eBPF / kernel code |
| `vantio` CLI enhancements | Modifications to the Phantom Engine loader |
| Python SDK improvements | Raw syscall hooks or IDS-style telemetry |
