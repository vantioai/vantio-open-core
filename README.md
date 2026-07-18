# vantio-open-core · Vantio Optics

**Vantio Optics** — See LLM egress. Blind by design, not a proxy.  
The Free · Open Core observe plane: intercept outbound LLM calls without code changes, capture metadata (never prompts), and export proof — **observe only, no enforce**.

This repo ships **Vantio Optics**. The same client runs in every tier; higher tiers unlock **Vantio Gate** (Pro · enforce) and **Vantio Phantom Engine** (Enterprise · absolute control) on top of Optics.

> **Vantio tiers unlock governance:**  
> **Vantio Optics** (Free · Open Core) → **Vantio Gate** (Pro) → **Vantio Phantom Engine** (Enterprise)

---

## Get started in 60 seconds

```bash
npm install -g @vantio/cli
vantio run node agent.js          # no key needed — Free Observe works immediately
```

No-install path:

```bash
npx @vantio/cli run node agent.js
```

Optionally connect to your dashboard (Pro/Enterprise features):

```bash
vantio login <your-api-key>       # validates + saves the key; no env vars needed
```

Grab your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard).

After a run, generate an auditor-ready proof artifact or explore local history:

```bash
vantio prove                      # HTML proof artifact (Free, no key needed)
vantio discover --local           # local run history (Free, no key needed)
vantio discover                   # full workspace history (Pro/Enterprise)
```

---

## Sight Loop (Optics workflow)

Optics ships one named workflow — **Sight Loop**:

1. **Wrap** — `vantio run` / SDK  
2. **Capture** — host · process · bytes · time · trace (no prompts/completions)  
3. **Inspect / export** — `vantio prove`, `vantio discover --local`, or **Optics MCP**  
4. **Honest residual** — ungoverned paths stay silent → upgrade cue  

Full walkthrough: [docs/sight-loop.md](./docs/sight-loop.md) · MCP: [docs/optics-mcp.md](./docs/optics-mcp.md) · Offline prove: `./scripts/sight-loop-prove.sh`

---

## Docs

| Doc | Purpose |
|-----|---------|
| [Dogfood Optics](./docs/dogfood-optics.md) | Local loop: `vantio run` → prove → Optics MCP |
| [Sight Loop](./docs/sight-loop.md) | Optics workflow (wrap → capture → inspect → residual) |
| [Optics MCP](./docs/optics-mcp.md) | Read-only MCP for agent hosts / IDEs |
| [Surfaces](./docs/surfaces.md) | Hooks, Action, Docker, webhooks + deeper earmarks |
| [Observe only — no enforce](./docs/observe-only.md) | Free-tier fence |
| [Getting started](./docs/getting-started-tier01.md) | 60-second quickstart |
| [Prove artifacts](./docs/prove.md) | `vantio prove` reference |
| [Framework integrations](./docs/framework-integrations.md) | LangChain, LlamaIndex, CrewAI, AutoGen |

---

## Packages

| Package | Description |
|---------|-------------|
| [`packages/vantio-cli`](./packages/vantio-cli) | CLI runner (`@vantio/cli`) |
| [`packages/vantio-optics-mcp`](./packages/vantio-optics-mcp) | Optics MCP (`@vantio/optics-mcp`) — observe only |
| [`packages/vantio-gate-mcp`](./packages/vantio-gate-mcp) | Gate MCP (`@vantio/gate-mcp`) — dry-run evaluate |
| [`packages/vantio-agent-sdk`](./packages/vantio-agent-sdk) | Node.js agent SDK (`@vantio/agent-sdk`) |
| [`packages/vantio-agent-sdk-py`](./packages/vantio-agent-sdk-py) | Python agent SDK (`vantio-agent-sdk`) |
| [`extensions/vantio-optics`](./extensions/vantio-optics) | Thin VS Code extension |
| [`integrations/hooks`](./integrations/hooks) | Cursor / Claude / OpenClaw hooks |

---

## Tier model — one platform, unlocked layers

| Tier | Feature layer | Repo |
|------|--------------|------|
| **Free** | **Vantio Optics** · Observe ← you are here | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) |
| **Pro** | + **Vantio Gate** · Enforce (block, redact, caps) | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) |
| **Enterprise** | + **Vantio Phantom Engine** · Absolute Control | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) |

Optics is the client at every tier. On Free (no Pro key), it **observes only** — events are labelled `OBSERVED`. With a Pro key, the same client fetches policy from [Vantio Gate](https://github.com/vantioai/vantio-pro) and can block, redact, or cap locally. Enterprise adds **Vantio Phantom Engine** beneath the app layer. See [observe-only.md](./docs/observe-only.md) for the Free-tier fence.

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

## Optics: honest about bypassability

`vantio run` intercepts LLM calls by patching `globalThis.fetch` in the Node process.
This covers the vast majority of agents without code changes.

**It can be bypassed** — by native socket calls, un-instrumented subprocesses, or
processes not started with `vantio run`. This is intentional. Optics surfaces your
governance gap; it does not paper over it.

- **Vantio Gate (Pro)** — Policy Latch: block, redact, caps, dashboard sync, fleet discovery. App layer.
- **Vantio Phantom Engine (Enterprise)** — Ring-0 eBPF TLS observe, Bypass Reconciliation when app and kernel diverge.

Use `vantio discover --local` to see what Free observes on your machine.
Use `vantio prove` to generate an auditor-ready proof artifact from any run.

---

---

## Telemetry

Anonymous, opt-out usage analytics. No prompts, completions, API keys, or emails. Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

[vantio.ai](https://vantio.ai) · [Dashboard](https://vantio.ai/dashboard) · [Pricing](https://vantio.ai/pricing) · MIT License
