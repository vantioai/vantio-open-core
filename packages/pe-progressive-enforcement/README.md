# @vantio/pe-progressive-enforcement

PRIVATE | INERT | NOT SHIPPED | NO HOST ATTACHMENT | NO AUTO-ENFORCE | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

In-process lifecycle for progressive enforcement. An observation can become a proposal. It cannot become enforced policy on its own. Reaching `ENFORCE` records a controlled promotion and an in-process match. This package does not attach that match to a host, patch `fetch`, load a kernel program, or change `@vantio/cli` 0.3.24 or `vantio-agent-sdk` 3.1.0.

`schema_status` is `unstable-pre-1.0`. Producer classification: `PE_PROGRESSIVE_ENFORCEMENT_READY_FOR_COUNCIL`. That token is the handoff to a separate council. It is not a council verdict.

Run from the repository root:

```sh
node --test tests/pe-progressive-enforcement/*.test.cjs
```

The package is not a pnpm workspace member and is not loaded by the live CLI, Node SDK, Python SDK, or MCP servers.
