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
    action_taken:  "POLICY_VIOLATION",
    pid:           process.pid,
  });
});
```

Requires `VANTIO_CLOUD_INGEST=true` and `VANTIO_API_KEY` to be set. Non-fatal — telemetry failures never crash your agent.

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
| `VANTIO_API_KEY` | Your API key from [vantio.ai/success](https://vantio.ai/success) |
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
