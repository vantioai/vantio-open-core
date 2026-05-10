# Vantio AI Contribution Matrix

We accept pull requests that adhere to strict deterministic engineering principles.

## Engineering Directives
1. **Zero State Leakage:** Server Actions and Edge APIs must strictly sanitize all inputs.
2. **Type Safety:** The `any` keyword is explicitly banned. Utilize `unknown` with type guards or `zod` schemas.
3. **Telemetry Quarantine:** No raw user prompts or PII may ever be passed to the `@vantio/agent-sdk` telemetry payload.
4. **Build Provenance:** All code must pass the GitHub Actions CI pipeline (`pnpm build`) without Next.js compilation warnings.
