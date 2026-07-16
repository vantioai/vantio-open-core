# vantio-open-core · Observe Layer

**Observe** — The Free-tier governance layer of the Vantio platform. Open Core intercepts every outbound LLM call your agent makes — without a proxy and without code changes — giving you complete visibility into all AI traffic from day one.

This repo is the **Observe feature plane**. It is the foundation that runs inside every tier: Free customers get observation alone; Pro and Enterprise customers get observation *plus* the enforcement layers those tiers unlock.

> **Vantio tiers unlock governance:**
> `Observe (Free · Open Core)` → `Enforce (Pro unlocked)` → `Absolute Control (Enterprise · Phantom Engine unlocked)`

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

## Tier model — one platform, unlocked layers

| Tier | Feature layer | Repo |
|------|--------------|------|
| **Free** | **Observe** ← you are here | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) |
| **Pro** | + **Enforce** (block, redact, caps) | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) |
| **Enterprise** | + **Absolute Control** (kernel eBPF) | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) |

Open Core is the client that runs at every tier. With a Free API key it observes. With a Pro API key it fetches policy from [Vantio Pro](https://github.com/vantioai/vantio-pro) and enforces locally — block, redact, and spend caps happen client-side, policy lives in the Pro control plane. Enterprise customers get all three layers active simultaneously; the dashboard shows all three columns because all three feature layers are running, not because three products compete to claim the event.

Full breakdown: [PRODUCT_LINEUP.md](../PRODUCT_LINEUP.md)

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

> On Ubuntu/Debian (23.04+), global `pip install` is blocked by default (PEP 668). Use a virtualenv or `pipx install vantio-agent-sdk` instead.

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
