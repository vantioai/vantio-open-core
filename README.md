# Vantio AI Open-Core

The deterministic Open-Core repository for the Vantio AI Tier-01 Control Plane.

## Architectural Matrix

Vantio Open-Core is engineered on a strict, mathematically sound technology stack:
- **Framework:** Next.js 15 (App Router) + React 19
- **Identity Gateway:** Auth.js v5 (NextAuth) mapped to custom enterprise schemas
- **Persistence:** Prisma ORM connected to PostgreSQL
- **Cognitive Engine:** Vercel AI SDK streaming `gpt-4o` with deterministic tool execution
- **Telemetry Quarantine:** Custom `@vantio/agent-sdk` enforcing edge-level data sanitization

## The Open-Core Schism

This repository demonstrates the strict isolation between application state and execution telemetry. Raw linguistic payloads are physically quarantined at the Next.js API boundary. The LLM retains persistent conversational memory, while the telemetry ledger strictly records metadata (token consumption, execution latency, model identity).

## Initialization Protocol

1. Ensure Docker Desktop is installed and running.
2. Ignite the local PostgreSQL substrate:
   `docker compose up -d`
3. Push the database schema:
   `pnpm dlx prisma db push`
4. Inject your cryptographic Tier-03 keys into `apps/oracle/.env.local`:
   - `OPENAI_API_KEY=sk-...`
   - `AUTH_SECRET=...`
5. Compile and run the Omniscient Oracle:
   `pnpm dev`
