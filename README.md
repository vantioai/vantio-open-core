# Vantio AI: Open-Core SDK & CLI (Tier 01)

The deterministic, open-source developer wedge for Vantio AI. Achieve zero-line terminal visibility into your autonomous AI agents in under 60 seconds.

## The Open-Core Schism
This repository represents Tier 01 of the Vantio architecture: the Developer open-core SDK and CLI. By design, this repository demonstrates total physical isolation of our public user-space SDKs from our proprietary Ring-0 IP (The Phantom Engine). Raw linguistic payloads are physically quarantined at the Next.js API boundary, securing systems without reading proprietary prompts.

## Architectural Matrix
* **Observability (The Wedge):** The `vantio run` compiled binary synchronously wraps user-space processes, dynamically injecting a cryptographic `VANTIO_TRACE_ID` without requiring AST modifications or complex integrations.
* **Framework:** Next.js 15 App Router (React 19 Compiler) providing local visualization.
* **Persistence:** Frictionless, ephemeral local SQLite substrate (`dev.db`) to guarantee sub-60-second Time-To-Value (TTV).
* **Dependency Governance:** Standard `npm` or `yarn` commands are strictly banned to prevent phantom dependency vulnerabilities. Toolchains enforce `pnpm` workspaces via `.npmrc`.
* **The Pro Bridge (Tier 2):** Ready for team-wide policy enforcement? Inject `VANTIO_CLOUD_INGEST=true` to seamlessly halt local SQLite writes and asynchronously route telemetry to the Vantio Managed Edge Proxy (Google Cloud Spanner).

## Initialization Protocol (60-Second TTV)

**1. Install strictly governed dependencies:**
```bash
pnpm install
```

**2. Scaffold the ephemeral local ledger (SQLite):**
```bash
cd apps/oracle && pnpm prisma db push
```

**3. Compile and execute the local visualizer:**
```bash
pnpm dev
```

**4. Secure your AI application instantly by wrapping your standard start command:**
```bash
vantio run node agent.js # or: vantio run python agent.py
```
