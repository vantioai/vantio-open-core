# @vantio/cli

> Run any AI agent with full observability. Zero code changes.

```bash
npm install -g @vantio/cli
```

---

## Usage

```bash
vantio run node agent.js
vantio run python agent.py
vantio run tsx agent.ts
```

Wrap any process with `vantio run`. The CLI automatically intercepts every outbound call to a known LLM API — OpenAI, Anthropic, Gemini, Cohere, Mistral, and more — and streams the metadata to your dashboard.

Your code doesn't change. Your agent runs normally.

---

## Flags

```bash
vantio run --audit node agent.js     # flag events as VANTIO_AUDIT_MODE=1
vantio run --summary node agent.js   # print a run summary on exit
```

**`--audit`** — marks all events from this run as audit mode. Useful when running agents in observation-only mode before enforcing policies.

**`--summary`** — prints a summary when the process exits:

```
[ ∅ VANTIO ] Run Summary
  LLM calls:    7
  Hosts:        api.openai.com, api.anthropic.com
  Total bytes:  94,201
  Duration:     12.4s
```

In free mode (no API key), intercepted calls print to the terminal in real time.

---

## Enforcement notes (Tier 2)

With a `VANTIO_API_KEY`, the interceptor loads a cloud policy and enforces it locally. A few semantics worth knowing:

- **Host scope** — policy applies to known LLM hosts plus any host named in `blocked_hosts`/`allowed_hosts`. `blocked_hosts` blocks **any** matching host (LLM or not); a non-empty `allowed_hosts` blocks any in-scope host not on the list. Unrelated traffic (OS, package managers, etc.) is never touched.
- **Spend cap** — the USD spend cap is **best-effort and per-process**. Bytes are estimated (request + response, including streamed responses counted after the fact), so the cap gates *subsequent* calls once the running total is crossed rather than aborting a call mid-stream, and it does not aggregate across processes.

---

## Environment variables

| Variable | Description |
|---|---|
| `VANTIO_API_KEY` | Your API key from [vantio.ai/success](https://vantio.ai/success) |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to route events to your dashboard |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to opt out of anonymous usage telemetry |
| `DO_NOT_TRACK` | Set to `1` to opt out of anonymous usage telemetry |

---

## Anonymous telemetry

Vantio sends a small **anonymous, opt-out** usage ping (a random id, runtime/OS, LLM hostnames, and counts) to help prioritize providers and runtimes. It never includes prompts, completions, API keys, or PII, and never blocks your agent. Opt out with `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

---

## Supported runtimes

Auto-intercepts LLM calls when running **Node.js** processes (`node`, `tsx`, `ts-node`, `npx`).

Python, Ruby, and other runtimes are spawned normally without interception — use the [Python SDK](https://pypi.org/project/vantio-agent-sdk) for those.

---

## Supported LLM providers

`api.openai.com` · `api.anthropic.com` · `generativelanguage.googleapis.com` · `api.cohere.ai` · `api.mistral.ai` · `api.groq.com` · `api.together.xyz` · `api.perplexity.ai` · `inference.ai.azure.com`

---

## SDK

For explicit trace correlation across async hops, use the SDK alongside the CLI:

```bash
npm install @vantio/agent-sdk
```

```ts
import { shield, reportAnomaly } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyAgent();
});
```

---

[vantio.ai](https://vantio.ai) · [Docs](https://vantio.ai/developers) · [Pricing](https://vantio.ai/pricing) · MIT License
