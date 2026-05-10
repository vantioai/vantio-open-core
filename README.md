# Vantio AI: Open-Core SDK & CLI (Tier 01)

The deterministic, open-source developer wedge for Vantio AI.

## The Open-Core Schism

This repository represents Tier 01 of the Vantio architecture: the Developer open-core SDK and CLI. By design, this repository demonstrates total physical isolation of our public user-space SDKs from our proprietary Ring-0 IP (The Phantom Engine). Raw linguistic payloads are physically quarantined at the Next.js API boundary, securing systems without reading proprietary prompts.

## Architectural Matrix

- **Framework:** Next.js 15 App Router (React 19 Compiler).
- **Identity Gateway:** Isolated local authentication shim via Auth.js (Note: Enterprise deployments utilize our `/auth/enterprise` SAML gateway to completely sever developer environments from institutional workspaces).
- **Persistence:** Local PostgreSQL substrate (Note: Production enterprise ledgers are natively mapped to WORM-compliant Google Cloud Spanner instances).
- **Dependency Governance:** Standard npm or yarn commands are banned to prevent phantom dependency vulnerabilities. Toolchains strictly enforce pnpm workspaces via `.npmrc`.

## Initialization Protocol (60-Second TTV)

The Tier-01 Control Plane requires zero infrastructure. It runs entirely in user-space with an ephemeral local datastore.

1. Configure local environment variables in `apps/oracle/.env.local` (Requires `OPENAI_API_KEY` and `AUTH_SECRET`).
2. Install dependencies:
   `pnpm install`
3. Ignite the frictionless wedge (This automatically provisions the ephemeral SQLite shim):
   `pnpm dev`
