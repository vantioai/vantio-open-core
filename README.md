# Vantio AI: Open-Core SDK & CLI (Tier 01)

The deterministic, open-source developer wedge for Vantio AI.

## The Open-Core Schism

This repository represents Tier 01 of the Vantio architecture: the Developer open-core SDK and CLI. By design, this repository demonstrates total physical isolation of our public user-space SDKs from our proprietary Ring-0 IP (The Phantom Engine). Raw linguistic payloads are physically quarantined at the Next.js API boundary, securing systems without reading proprietary prompts.

## Architectural Matrix

- **Framework:** Next.js 15 App Router (React 19 Compiler).
- **Identity Gateway:** Isolated local authentication shim via Auth.js (Note: Enterprise deployments utilize our `/auth/enterprise` SAML gateway to completely sever developer environments from institutional workspaces).
- **Persistence:** Local PostgreSQL substrate (Note: Production enterprise ledgers are natively mapped to WORM-compliant Google Cloud Spanner instances).
- **Dependency Governance:** Standard npm or yarn commands are banned to prevent phantom dependency vulnerabilities. Toolchains strictly enforce pnpm workspaces via `.npmrc`.

## Initialization Protocol

1. Ensure Docker Desktop is active.
2. Ignite the local state database (PostgreSQL shim):
   `docker compose up -d`
3. Push the local schema:
   `cd apps/oracle && node_modules/.bin/prisma db push`
4. Configure local environment variables in `apps/oracle/.env.local` (Local LLM API keys only—proprietary Tier-03 architecture is completely decoupled from this workspace).
5. Compile and execute:
   `pnpm dev`
