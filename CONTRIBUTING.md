# Vantio AI Contribution Matrix

We accept pull requests that adhere to strict, deterministic engineering principles. By contributing to this repository, you acknowledge and agree to abide by the following architectural boundaries.

## The Open-Core Schism
**WARNING:** This repository (`vantio-open-core`) represents Tier-01 of the Vantio architecture. It is strictly limited to user-space CLI tooling and the Next.js visualizer.
* Do not submit pull requests that attempt to introduce kernel-level interception (eBPF), Ring-0 logic, or modifications intended for the proprietary Tier-03 Phantom Engine.
* Features must remain entirely localized to the ephemeral SQLite execution path or the Tier-02 cloud routing SDK.

## Engineering Directives

* **Payload Quarantine:** No raw user prompts, linguistic responses, or PII may ever be passed to the `@vantio/agent-sdk` telemetry payload. Raw memory pointers must be severed at the API boundary.
* **Type Safety:** The `any` keyword is explicitly banned across the entire TypeScript codebase. Utilize `unknown` paired with strict type guards or `zod` schemas. PRs containing `any` will be automatically rejected.
* **Dependency Governance:** `pnpm` is the only authorized package manager for this workspace. Standard `npm` or `yarn` commands are structurally banned to prevent phantom dependency vectors. Do not commit `package-lock.json` or `yarn.lock` files.
* **Build Provenance & CI/CD:** All code must pass the GitHub Actions CI pipeline (`pnpm build`) with zero Next.js compilation warnings. Merged code must successfully trigger the SLSA L3 Sigstore provenance attestation.
