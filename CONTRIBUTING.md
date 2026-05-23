# Vantio AI — Contribution Matrix

By submitting a pull request you acknowledge and agree to these architectural boundaries.

## The Open-Core Schism

**This repository (`vantio-open-core`) is strictly Ring-3 user-space.** Do not submit PRs that introduce:

- eBPF programs, kernel probes, or any Ring-0 logic
- References to `/sys/fs/bpf/`, `bpf_*` helpers, or `aya-ebpf`
- Imports from or dependencies on the proprietary `vantio-phantom-engine` repository

Violations are automatically rejected by CI.

## Engineering Directives

**Type Safety**  
The `any` keyword is banned across the entire TypeScript codebase. Use `unknown` with strict type guards or `zod` schemas. PRs containing `any` will not be merged.

**Payload Quarantine**  
No raw user prompts, LLM responses, or PII may be passed to the `@vantio/agent-sdk` telemetry payload or written to the Supabase ledger. Strip all linguistic content at the API boundary before ingestion.

**Dependency Governance**  
`pnpm` is the only authorized package manager. `npm install` and `yarn` are banned to prevent phantom dependency vectors. Do not commit `package-lock.json` or `yarn.lock`.

**Build Compliance**  
All PRs must pass the GitHub Actions CI pipeline (`pnpm build`) with zero Next.js compilation errors or warnings. Merges to `main` trigger the SLSA L3 Sigstore provenance attestation — your artifact must be reproducibly buildable.

**Supabase Schema Changes**  
Any migration that alters the `tenants`, `anomaly_events`, or `enterprise_leads` tables must be reviewed by a maintainer. Changes to column types or primary keys are breaking changes and require a major version bump in the affected package.

## What belongs here

| ✅ In scope | ❌ Out of scope |
|---|---|
| `@vantio/agent-sdk` improvements | eBPF / kernel code |
| `vantio` CLI enhancements | Modifications to the Phantom Engine loader |
| Next.js control plane features | Direct Spanner writes (enterprise tier only) |
| Supabase schema migrations (with review) | Auth.js / SAML plumbing |
| `@vantio/edge-proxy` Spanner mutation helpers | Raw syscall hooks or IDS-style telemetry |
