# vantio-open-core · Vantio Optics

[![CI](https://github.com/vantioai/vantio-open-core/actions/workflows/ci.yml/badge.svg)](https://github.com/vantioai/vantio-open-core/actions/workflows/ci.yml)

**Vantio Optics** is free visibility into what your agents send. Wrap a process with `vantio run`, see outbound LLM calls (host, size, process, time — never prompts), and export a proof. Observe only — Free does not block, redact, or cap spend.

The same client runs with every product. **Vantio Gate** ($499) adds rules that stick on the agent path. **Vantio Phantom Engine** ($799 per node) protects Linux machines you own — enforce and control together, one purchase. Do not stack Gate cloud on a Phantom Engine quote.

> **Optics** (Free) · **Gate** ($499) · **Phantom Engine** ($799/node) · **Phantom Engine Enterprise** (talk to sales)

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

Optionally connect a Gate key (paid features):

```bash
vantio login <your-api-key>       # validates + saves the key; no env vars needed
```

Free Optics needs no key. Paid keys come from a Gate trial (`hello@vantio.ai` today)
or Stripe Checkout once live — there is no public self-serve key dashboard yet
(`/dashboard` redirects to docs). See [vantio.ai/pricing](https://vantio.ai/pricing).

After a run, generate an auditor-ready proof artifact or explore local history:

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
4. **Honest residual** — paths that never hit the interceptor stay unnamed here → upgrade cue  

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

## Suite — peer products

| Product | Job | List | Repo |
|---------|-----|------|------|
| **Vantio Optics** | Observe ← you are here | Free | [`vantioai/vantio-open-core`](https://github.com/vantioai/vantio-open-core) |
| **Vantio Gate** | Enforce — rules you set, where the agent is wired | $499/month | [`vantioai/vantio-pro`](https://github.com/vantioai/vantio-pro) |
| **Vantio Phantom Engine** | Protect machines you own — enforce and control together | $799/node | [`vantioai/vantio-phantom-engine`](https://github.com/vantioai/vantio-phantom-engine) |
| **Phantom Engine Enterprise** | Governance on that protection (ledger, evidence, process) | Talk to sales | same |

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

## Optics: honest about what it covers

`vantio run` intercepts LLM calls by patching `globalThis.fetch` in the Node process.
That covers most agents without code changes.

Native sockets, un-instrumented subprocesses, or processes not started with `vantio run`
never hit Optics — and Optics does not invent a record for them. That residual is the
upgrade cue:

- **Vantio Gate** — when an agent crosses a line you already set on the wrapped path, Gate can stop the request, strip sensitive details before they leave, or put a hard limit on spend.
- **Vantio Phantom Engine** — protection on Linux machines you own. Enforce and control together, one purchase. **Rogue Reconciliation** names the gap when the host sees traffic the app layer never recorded.

Use `vantio discover --local` to see what Free observes on your machine.
Use `vantio prove` to generate an auditor-ready proof artifact from any run.

---

## Telemetry

Anonymous, opt-out usage analytics. No prompts, completions, API keys, or emails. Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

[vantio.ai](https://vantio.ai) · [Dashboard](https://vantio.ai/dashboard) · [Pricing](https://vantio.ai/pricing) · MIT License
