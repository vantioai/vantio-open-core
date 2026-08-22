# @vantio/agent-sdk

**Vantio** is the infrastructure control layer for autonomous AI. This package is **Vantio Optics** Observe for Node: a trace ID around your agent. It does not wrap `fetch` by itself — Node wrap lives in [`@vantio/cli`](https://www.npmjs.com/package/@vantio/cli) (`vantio run`).

Optics does not block on its own. [Gate](https://github.com/vantioai/vantio-pro) enforces rules on the wrapped path. [Phantom Engine](https://github.com/vantioai/vantio-phantom-engine) is runtime protection on enrolled Linux.

```bash
npm install @vantio/agent-sdk
```

## Quick start

```ts
import { shield } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyLLMAgent();
});
```

Wrap your agent in `shield()`. Vantio generates a trace ID and propagates it through async hops — without reading your prompts. Node LLM wrap (fetch, undici, http/https, …) is `vantio run` from `@vantio/cli`, not this package.

---

## API

### `shield(callback, options?)` — trace context

```ts
import { shield } from "@vantio/agent-sdk";

const result = await shield(async () => {
  return await runMyAgent();
});

// With options:
await shield(async () => { ... }, {
  traceId: "custom-uuid",   // optional — generated if omitted
});
```

`withVantio()` is an alias for `shield()` — use either.

---

### `reportAnomaly(event, opts?)` — send metadata to Gate ingest

```ts
import { shield, reportAnomaly } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyAgent();

  await reportAnomaly({
    target_host:   "api.openai.com",
    bytes_severed: 14382,
    // VantioActionTaken: "OBSERVED" | "ALLOWED" | "REDACTED" | "BLOCKED_HOST" | "BLOCKED_SIZE" | "BLOCKED_SPEND"
    action_taken:  "BLOCKED_HOST",
    pid:           process.pid,
  });
});
```

Requires `VANTIO_CLOUD_INGEST=true` and `VANTIO_API_KEY` to be set. Non-fatal — telemetry failures never crash your agent.

---

## Policy & redaction (Vantio Gate)

Enforcement policy is served by the [Vantio Pro](https://github.com/vantioai/vantio-pro) control plane; the SDK applies it **locally** — Vantio is not a network proxy. The SDK ships two building blocks so you can fetch and enforce that policy yourself.

### `fetchPolicy(apiKey, opts?)` — load the cloud-managed policy

```ts
import { fetchPolicy, type VantioPolicy } from "@vantio/agent-sdk";

const policy: VantioPolicy = await fetchPolicy(process.env.VANTIO_API_KEY!);
// { enforce, redact_pii, pii_types, allowed_hosts,
//   blocked_hosts, max_request_bytes, spend_cap_usd }
```

GETs `/api/v1/config` with the `x-vantio-identity` header. **Fails open:** on any error — network failure, non-2xx, malformed body, or timeout — it returns a permissive copy of `DEFAULT_POLICY` so an unreachable control plane can never block your agent. Options: `ingestUrl`, `timeoutMs` (default 5000), `signal`.

### `redactPII(text, piiTypes?)` — strip PII locally

```ts
import { redactPII } from "@vantio/agent-sdk";

const { text, redactions } = redactPII("ssn 123-45-6789, mail a@b.com");
// text       → "ssn [VANTIO_REDACTED:SSN], mail [VANTIO_REDACTED:EMAIL]"
// redactions → ["ssn", "email"]
```

A pure, side-effect-free function — **nothing ever leaves your process.** Supports `ssn`, `email`, `credit_card`, and `phone` (defaults to all four), using the same patterns and `[VANTIO_REDACTED:LABEL]` tokens as the CLI interceptor.

The `VantioActionTaken` union (`"OBSERVED" | "ALLOWED" | "REDACTED" | "BLOCKED_HOST" | "BLOCKED_SIZE" | "BLOCKED_SPEND"`) is also exported for typing your own enforcement reporting.

---

### `getCurrentTraceId()` — read the active trace ID

```ts
import { getCurrentTraceId } from "@vantio/agent-sdk";

await shield(async () => {
  const id = getCurrentTraceId(); // always defined inside shield()
  console.log(`Trace: ${id}`);
});

getCurrentTraceId(); // undefined — outside shield() frame
```

---

## Environment variables

| Variable | Description |
|---|---|
| `VANTIO_API_KEY` | Gate API key from a trial (`hello@vantio.ai`) or Stripe once live — `/dashboard` redirects to docs |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to enable cloud routing |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode |

---

## Zero-line Node wrap

No code changes for Node — use the CLI:

```bash
npx @vantio/cli run node agent.js
```

Python needs [`vantio-agent-sdk`](https://pypi.org/project/vantio-agent-sdk) on that interpreter. Prefixing `vantio run python` does not intercept by itself.

---

## What gets captured

- Which LLM endpoint was called
- Response size in bytes
- Process ID and timestamp
- A trace ID linking all calls in the same agent run

**What never gets captured:** prompts, completions, or any content from your requests.

---

[vantio.ai](https://vantio.ai) · [Optics](https://vantio.ai/optics) · [Pricing](https://vantio.ai/pricing) · MIT License
