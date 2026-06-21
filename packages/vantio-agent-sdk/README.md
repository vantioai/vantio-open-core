# @vantio/agent-sdk

> See what your AI agents are doing. Two lines of code.

```bash
npm install @vantio/agent-sdk
```

---

## Quick start

```ts
import { shield } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyLLMAgent();
});
```

Wrap your agent in `shield()`. Vantio generates a trace ID, propagates it through every async hop in your agent's call tree, and streams metadata to your dashboard — without ever reading your prompts.

---

## API

### `shield(callback, options?)` — canonical interceptor

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

### `reportAnomaly(event, opts?)` — send metadata to your dashboard

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

## Policy & redaction (Tier 2)

Tier 2 enforcement runs **locally** in the SDK/CLI — Vantio is not a network proxy. The SDK ships two building blocks so you can enforce a cloud-managed policy yourself.

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
| `VANTIO_API_KEY` | Your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard) |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to enable cloud routing |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode |

---

## Zero-line alternative

No code changes at all — use the CLI:

```bash
npx @vantio/cli run node agent.js
```

---

## What gets captured

- Which LLM endpoint was called
- Response size in bytes
- Process ID and timestamp
- A trace ID linking all calls in the same agent run

**What never gets captured:** prompts, completions, or any content from your requests.

---

[vantio.ai](https://vantio.ai) · [Docs](https://vantio.ai/developers) · [Pricing](https://vantio.ai/pricing) · MIT License
