# @vantio/cli

[![npm](https://img.shields.io/npm/v/@vantio/cli.svg)](https://www.npmjs.com/package/@vantio/cli)

> Wrap any AI agent with **Vantio Optics** — free visibility into what it sends. Zero code changes. Current npm release: **0.3.6**.

```bash
npm install -g @vantio/cli
# or:
curl -fsSL https://vantio.ai/install.sh | sh
```

---

## Quick start

```bash
vantio run node agent.js        # Free Observe — no key needed
vantio login <your-api-key>     # optional — Gate / paid features
```

`vantio login` validates your key against `https://vantio.ai/api/v1/config` and, on success, stores it at `~/.vantio/config.json` (chmod `600`). After that, `vantio run` injects it automatically — no `VANTIO_API_KEY` juggling. Free Optics needs no key. Paid Gate keys come from a trial (`hello@vantio.ai`) or Stripe once live — there is no public self-serve key dashboard yet (`/dashboard` redirects).

---

## Commands

```bash
vantio login [key]    # save & validate your API key (prompts if omitted; input masked on a TTY)
vantio logout         # remove the stored key
vantio whoami         # show the stored key (masked) + live connection status
vantio run <program>  # spawn a program under the Vantio execution context
vantio discover       # show your Shadow AI attack surface (Pro / Enterprise)
vantio prove          # generate an auditor-ready proof artifact from a run log (Free)
```

`login` refuses to save a key the server rejects (HTTP 401). The full key is never printed — `whoami` and login output only ever show a masked form like `vk_liv…a1b2`.

---

## Usage

```bash
vantio run node agent.js
vantio run python agent.py
vantio run tsx agent.ts
```

Wrap any Node process with `vantio run`. The CLI intercepts outbound calls to known LLM APIs via Node `fetch`, `undici.fetch`, `undici.request` (including `Client` / `Pool` / `Agent` `.request()`), `undici.stream` / `pipeline` / `dispatch`, and Node `http`/`https`, and records connection metadata locally (and to Gate when a key is configured). For Python, install `vantio-agent-sdk` and run `vantio run python agent.py` — same wrap, no script edit. `shield()` is optional when you want a trace id inside the process.

Your code doesn't change. Your agent runs normally. If you've run `vantio login`, the stored key is injected into the child process; an explicit `VANTIO_API_KEY` in your environment always takes precedence.

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
  → Run `vantio login` to enforce policy and persist events.
```

In free mode (no API key), intercepted calls print to the terminal in real time.

---

## vantio prove — Auditor-Ready Proof Artifacts (Free)

```bash
vantio prove                           # HTML report — most recent run
vantio prove --list                    # list all local run logs
vantio prove --run=<trace-id>          # report for a specific run
vantio prove --format=md               # Markdown to stdout
vantio prove --format=html --out=proof.html
```

`vantio prove` reads the run logs that `vantio run` automatically writes to
`~/.vantio/runs/` and generates a self-contained proof document. Reports include
trace IDs, machine/PID, byte counts, host breakdown, and action labels.

**Reports contain zero prompts or completions** — safe to share with auditors.

Available on Free — no API key required. Full reference: [`docs/prove.md`](../../docs/prove.md)

---

## vantio discover — Shadow AI Attack Surface

```bash
vantio discover [--since=24h|7d|30d] [--host=<hostname>] [--json]
vantio discover --local                # Free-tier: local run logs only, no key needed
```

Shows every AI agent call recorded in your Vantio workspace, grouped by target host. Answers the question: **"What AI agents are running in my environment, and are they all governed?"**

- **Free (--local)** — reads local run logs from `~/.vantio/runs/`. No API key needed. Covers only processes started with `vantio run` on this machine.
- **Pro users** — see all SDK-monitored LLM calls with governance status (`OBSERVED` / `ALLOWED` / `REDACTED` / `BLOCKED`).
- **Enterprise users (Phantom Engine)** — additionally surfaces processes that called LLM endpoints without a Vantio `trace_id` — the **Shadow AI** agents that have no governance coverage.

```
Shadow AI Attack Surface — last 7d
------------------------------------------------------------------------
TARGET HOST                       CALLS    ALLOWED   REDACTED  BLOCKED   OBSERVED  SHADOW?   LAST SEEN
------------------------------------------------------------------------
api.openai.com                    142      138       3         0         1         ⚠ YES     2026-06-17 09:12:04 UTC
api.anthropic.com                 57       57        0         0         0         no        2026-06-17 14:33:21 UTC
------------------------------------------------------------------------
2 host(s) shown  |  ⚠  1 Shadow AI indicator(s) detected
```

**Options:**

| Flag | Description |
|---|---|
| `--since=<period>` | Look back `24h`, `7d`, or `30d` (default: `24h`) |
| `--host=<hostname>` | Filter to a specific target host |
| `--json` | Output raw JSON instead of a formatted table |
| `--local` | Local run logs only — no API key required (Free tier) |

Run `vantio discover --help` for full documentation.

> **Full discovery** requires a Pro or Enterprise account. `--local` works on Free without any key.

---

## Enforcement (Vantio Gate)

With a Gate `VANTIO_API_KEY`, the interceptor fetches policy from the [Vantio Gate](https://github.com/vantioai/vantio-pro) control plane and enforces it locally in your process. A few semantics worth knowing:

- **Host scope** — policy applies to known LLM hosts plus any host named in `blocked_hosts`/`allowed_hosts`. `blocked_hosts` blocks **any** matching host (LLM or not); a non-empty `allowed_hosts` blocks any in-scope host not on the list. Unrelated traffic (OS, package managers, etc.) is never touched.
- **Spend cap** — the USD spend cap is **best-effort and per-process**. Bytes are estimated (request + response, including streamed responses counted after the fact), so the cap gates *subsequent* calls once the running total is crossed rather than aborting a call mid-stream, and it does not aggregate across processes.

---

## Environment variables

| Variable | Description |
|---|---|
| `VANTIO_API_KEY` | Your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard) |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to opt out of anonymous usage telemetry |
| `DO_NOT_TRACK` | Set to `1` to opt out of anonymous usage telemetry |

---

## Anonymous telemetry

Vantio sends a small **anonymous, opt-out** usage ping (a random id, runtime/OS, LLM hostnames, and counts) to help prioritize providers and runtimes. It never includes prompts, completions, API keys, or PII, and never blocks your agent. Opt out with `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1`.

---

## Supported runtimes

Auto-intercepts LLM calls when running **Node.js** processes (`node`, `tsx`, `ts-node`, `npx`) — Node `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch`, and Node `http`/`https`. Current npm release: **`@vantio/cli` 0.3.6**.

Python, Ruby, and other runtimes are spawned normally without this interceptor — use the [Python SDK](https://pypi.org/project/vantio-agent-sdk) (`vantio-agent-sdk` **3.0.4**, `shield()`) for Python urllib / requests / httpx / aiohttp.

---

## Supported LLM providers

OpenAI (including regional), Anthropic, Google Gemini, Azure OpenAI, Azure AI, Cohere, Mistral, Groq, Together AI, Perplexity, xAI, DeepSeek, Fireworks, OpenRouter, Cerebras, Voyage AI, SambaNova, DeepInfra, Amazon Bedrock, Google Vertex AI, Hugging Face Inference, Replicate, Ollama, hosted NVIDIA NIM.

curl, raw sockets, undici.connect / upgrade, and browser paths stay outside this wrap. Phantom Engine is the Linux-host product when you need protection beneath the app wrap.

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

[vantio.ai](https://vantio.ai) · [Optics](https://vantio.ai/optics) · [Pricing](https://vantio.ai/pricing) · MIT License
