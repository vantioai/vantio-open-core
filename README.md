# vantio-open-core

Vantio intercepts every outbound LLM call your agent makes — without a proxy and without code changes — so you can see, redact, and enforce policy on AI traffic from day one.

---

## Get started in 60 seconds

```bash
npm install -g @vantio/cli
vantio login          # validates + saves your API key once
vantio run node agent.js
```

No-install path:

```bash
npx @vantio/cli run node agent.js
```

After `vantio login`, any process you start with `vantio run` is automatically observed. Grab your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard).

---

## Packages

| Package | Description |
|---------|-------------|
| [`packages/vantio-cli`](./packages/vantio-cli) | CLI runner (`@vantio/cli`) |
| [`packages/vantio-agent-sdk`](./packages/vantio-agent-sdk) | Node.js agent SDK (`@vantio/agent-sdk`) |
| [`packages/vantio-agent-sdk-py`](./packages/vantio-agent-sdk-py) | Python agent SDK (`vantio-agent-sdk`) |

---

## Tiers

| Tier | What you get | How |
|------|-------------|-----|
| **Tier 1 — Observe** (free) | See every LLM call: host, bytes, timestamp, trace ID | `vantio run` or `@shield` |
| **Tier 2 — Enforce** (Pro) | Block hosts, redact PII, spend caps, cloud-managed policy | API key + `vantio run` or `@shield` |
| **Tier 3 — Kernel** (Enterprise) | Shadow AI detection of unenrolled processes, eBPF | Phantom Engine |

---

## SDK — explicit trace correlation

### Node.js

```bash
npm install @vantio/agent-sdk
```

```ts
import { shield } from "@vantio/agent-sdk";

await shield(async () => {
  await runMyLLMAgent();
});
```

### Python

```bash
pip install vantio-agent-sdk
```

```python
from vantio import shield

@shield
async def run_agent():
    await call_openai(prompt)
```

---

## Supported LLM providers

`api.openai.com` · `api.anthropic.com` · `generativelanguage.googleapis.com` · `api.cohere.ai` · `api.mistral.ai` · `api.groq.com` · `api.together.xyz` · `api.perplexity.ai` · `inference.ai.azure.com`

---

## What gets captured

- Which LLM endpoint was called
- Response size in bytes
- The process ID
- A trace ID that links calls across your agent's full execution

**What never gets captured:** prompts, completions, or any content from your requests.

---

## Telemetry

Anonymous, opt-out usage analytics. No prompts, completions, API keys, or emails. Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

[vantio.ai](https://vantio.ai) · [Dashboard](https://vantio.ai/dashboard) · [Pricing](https://vantio.ai/pricing) · MIT License
