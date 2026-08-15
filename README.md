# vantio-open-core · Vantio Optics

[![CI](https://github.com/vantioai/vantio-open-core/actions/workflows/ci.yml/badge.svg)](https://github.com/vantioai/vantio-open-core/actions/workflows/ci.yml)
[![npm @vantio/cli](https://img.shields.io/npm/v/@vantio/cli.svg)](https://www.npmjs.com/package/@vantio/cli)
[![PyPI vantio-agent-sdk](https://img.shields.io/pypi/v/vantio-agent-sdk.svg)](https://pypi.org/project/vantio-agent-sdk/)

**Vantio Optics** is free visibility into what your agents send. Wrap a process, see outbound LLM calls (host, size, process, time — never prompts), and export a proof. Observe only — Free does not block, redact, or cap spend.

Vantio AI is a Pittsburgh-based cybersecurity startup founded in 2026. Optics helps you see. Gate applies the rules you set. Phantom Engine protects the machines you own — enforce and control together, one purchase. Phantom Engine Enterprise adds governance when you need proof and process on top.

> **Optics** (Free) · **Gate** ($499) · **Phantom Engine** ($799/node) · **Phantom Engine Enterprise** (talk to sales → ~$2k/node)

Current published wraps: **`@vantio/cli` 0.3.6** (npm) and **`vantio-agent-sdk` 3.0.4** (PyPI). The Node SDK `@vantio/agent-sdk` stays 0.2.1 — Node wrap lives in the CLI interceptor.

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

Python agents use `shield()` from `vantio-agent-sdk` 3.0.4 (urllib always; requests, httpx, and aiohttp when those libraries are already installed):

```bash
pip install vantio-agent-sdk==3.0.4
```

Optionally connect a Gate key (paid features):

```bash
vantio login <your-api-key>       # validates + saves the key; no env vars needed
```

Free Optics needs no key. Paid keys come from a Gate trial (`hello@vantio.ai` today)
or Stripe Checkout once live — there is no public self-serve key dashboard yet
(`/dashboard` redirects to docs). See [vantio.ai/pricing](https://vantio.ai/pricing).

After a run, export a proof artifact or explore local history:

```bash
vantio prove                      # HTML proof artifact (Free, no key needed)
vantio discover --local           # local run history (Free, no key needed)
vantio discover                   # full workspace history (Gate / Phantom Engine)
```

---

## Sight Loop (Optics workflow)

Optics ships one named workflow — **Sight Loop**:

1. **Wrap** — `vantio run` / SDK
2. **Capture** — host · process · bytes · time · trace (no prompts/completions)
3. **Inspect / export** — `vantio prove`, `vantio discover --local`, or **Optics MCP**
4. **Honest gap** — paths that never hit the interceptor stay unnamed here

Full walkthrough: [docs/sight-loop.md](./docs/sight-loop.md) · MCP: [docs/optics-mcp.md](./docs/optics-mcp.md) · Offline check: `./scripts/sight-loop-prove.sh`

---

## Docs

| Doc | Purpose |
|-----|---------|
| [Local Optics loop](./docs/dogfood-optics.md) | `vantio run` → proof → Optics MCP |
| [Sight Loop](./docs/sight-loop.md) | Optics workflow (wrap → capture → inspect) |
| [Optics MCP](./docs/optics-mcp.md) | Read-only MCP for agent hosts / IDEs |
| [Surfaces](./docs/surfaces.md) | Hooks, Action, Docker, webhooks |
| [Observe only — no enforce](./docs/observe-only.md) | Free-tier fence |
| [Getting started](./docs/getting-started-tier01.md) | 60-second quickstart |
| [Proof artifacts](./docs/prove.md) | `vantio prove` reference |
| [Framework integrations](./docs/framework-integrations.md) | LangChain, LlamaIndex, CrewAI, AutoGen |

---

## Packages

| Package | Published | Description |
|---------|-----------|-------------|
| [`packages/vantio-cli`](./packages/vantio-cli) | `@vantio/cli` **0.3.6** | CLI runner — Node fetch, undici.fetch, undici.request, stream/pipeline/dispatch, http/https wrap |
| [`packages/vantio-agent-sdk-py`](./packages/vantio-agent-sdk-py) | `vantio-agent-sdk` **3.0.4** | Python `shield()` — urllib + optional requests/httpx/aiohttp |
| [`packages/vantio-agent-sdk`](./packages/vantio-agent-sdk) | `@vantio/agent-sdk` **0.2.1** | Node.js `shield()` for trace correlation |
| [`packages/vantio-optics-mcp`](./packages/vantio-optics-mcp) | `@vantio/optics-mcp` | Optics MCP — observe only |
| [`packages/vantio-gate-mcp`](./packages/vantio-gate-mcp) | `@vantio/gate-mcp` | Gate MCP — dry-run evaluate |
| [`extensions/vantio-optics`](./extensions/vantio-optics) | | Thin VS Code extension |
| [`integrations/hooks`](./integrations/hooks) | | Cursor / Claude / OpenClaw hooks |

---

## Suite — peer products

| Product | Job | List | Repo |
|---------|-----|------|------|
| **Vantio Optics** | Observe ← you are here | Free | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) |
| **Vantio Gate** | Enforce — rules you set, where the agent is wired | $499/month | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) |
| **Vantio Phantom Engine** | Protect machines you own — enforce and control together | $799/node | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) |
| **Phantom Engine Enterprise** | Governance on that protection (ledger, evidence, process) | Talk to sales → ~$2k/node | same |

Optics is the client at every product. On Free (no Gate key), it **observes only** — events are labelled `OBSERVED`. With a Gate key, the same client fetches policy from [Vantio Gate](https://github.com/vantioai/vantio-pro) and can refuse a destination, strip sensitive fields, or cap spend on the wrapped path. Phantom Engine is a separate purchase for Linux hosts you enroll — not a leftover after Optics and Gate. See [observe-only.md](./docs/observe-only.md) for the Free-tier fence.

Full breakdown: [docs/PRODUCT_LINEUP.md](./docs/PRODUCT_LINEUP.md) · [vantio.ai/pricing](https://vantio.ai/pricing)

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

Node wrap of `fetch`, undici, and `http`/`https` is in **`@vantio/cli` 0.3.6** (`vantio run`). Use `shield()` when you want a trace ID across async hops.

### Python

```bash
pip install vantio-agent-sdk==3.0.2
```

> On Ubuntu/Debian (23.04+), global `pip install` is blocked by default (PEP 668). Use a virtualenv or `pipx install vantio-agent-sdk` instead.

```python
from vantio import shield

@shield
async def run_agent():
    await call_openai(prompt)
```

While `shield()` is active, Optics records urllib to in-scope hosts. If `requests`, `httpx`, or `aiohttp` are already installed, those are recorded the same way.

---

## Supported wraps

**Node (`vantio run`):** `fetch`, `undici.fetch`, `undici.request` (including Client / Pool / Agent), `undici.stream` / `pipeline` / `dispatch`, and Node `http` / `https`.

**Python (`shield()`):** `urllib`; `requests`, `httpx`, and `aiohttp` when those libraries are already installed.

**Phantom Engine:** Linux hosts you own.

**Providers:** OpenAI (including regional), Anthropic, Google Gemini, Azure OpenAI, Azure AI, Cohere, Mistral, Groq, Together AI, Perplexity, xAI, DeepSeek, Fireworks, OpenRouter, Cerebras, Voyage AI, SambaNova, DeepInfra, Amazon Bedrock, Google Vertex AI, Hugging Face Inference, Replicate, Ollama, hosted NVIDIA NIM.

curl, raw sockets, and browser paths stay outside this wrap.

---

## What gets captured

- Which LLM endpoint was called
- Response size in bytes
- The process ID
- A trace ID that links calls across your agent's full execution

**What never gets captured:** prompts, completions, or any content from your requests.

---

## Optics: honest about what it covers

`vantio run` intercepts LLM calls by wrapping Node `fetch` and Node `http`/`https`.
That covers most Node agents without code changes.

Native sockets, un-instrumented subprocesses, curl, browser paths, or processes not
started with `vantio run` / `shield()` never hit Optics — and Optics does not invent
a record for them.

- **Vantio Gate** — when an agent crosses a line you already set on the wrapped path, Gate can stop the request, strip sensitive details before they leave, or put a hard limit on spend.
- **Vantio Phantom Engine** — protection on Linux machines you own. Enforce and control together, one purchase.

Use `vantio discover --local` to see what Free observes on your machine.
Use `vantio prove` to export a proof artifact from any run.

---

## Telemetry

Anonymous, opt-out usage analytics. No prompts, completions, API keys, or emails. Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

[vantio.ai](https://vantio.ai) · [Optics](https://vantio.ai/optics) · [Pricing](https://vantio.ai/pricing) · MIT License
