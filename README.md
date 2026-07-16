# vantio-open-core

**Sees everything** — Open Core is the free developer layer of the Vantio suite. It intercepts every outbound LLM call your agent makes — without a proxy and without code changes — so you have complete visibility into all AI traffic from day one.

Open Core is the observe tier. Enforcement (block, redact, spend caps) requires [Vantio Pro](https://github.com/vantioai/vantio-pro). Kernel-level absolute control requires [Phantom Engine](https://github.com/vantioai/vantio-phantom-engine).

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

## Product lineup

| Product | Repository | Promise |
|---------|------------|---------|
| **Open Core** ← you are here | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) | **Sees everything** — observe all agent/LLM traffic |
| **Pro** | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) | **Enforces** — block, redact, caps; dashboard shows what policy stops |
| **Phantom Engine** | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) | **Absolute control** — fewer events, inescapable kernel catch |
| **Enterprise suite** | all three together | Full stack: observe + enforce + absolute control |

**Open Core alone** = observe tier. With a Pro API key the CLI fetches policy from [Vantio Pro](https://github.com/vantioai/vantio-pro) and enforces it locally — block, redact, and spend caps happen client-side, policy lives in the Pro control plane. Enterprise customers get all three products as a suite.

Full breakdown: [docs/PRODUCT_LINEUP.md](docs/PRODUCT_LINEUP.md)

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
