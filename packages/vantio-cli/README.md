# @vantio/cli

[![npm](https://img.shields.io/npm/v/@vantio/cli.svg)](https://www.npmjs.com/package/@vantio/cli)

> Wrap a Node agent with **Vantio Optics** — free visibility into what it sends. Current local candidate: **0.3.21** (remediation branch; not yet published). Python support requires `vantio-agent-sdk`. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state.

```bash
npm install -g @vantio/cli
```

There is no curl installer at `https://vantio.ai/install.sh`. [vantio.ai/install](https://vantio.ai/install) goes to the install docs. Python support requires `vantio-agent-sdk`. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state.

---

## Quick start

### Step 1 — Install

```bash
npm install -g @vantio/cli
```

That's the only install step. Works on macOS, Linux, and Windows (WSL).

### Step 2 — Run your agent

Instead of running your Node agent directly, prefix it with `vantio run`:

```bash
# Before
node agent.js

# After
vantio run node agent.js
```

Python: install `vantio-agent-sdk` first, then `vantio run python agent.py`. Prefixing `vantio run python` does not intercept by itself.

### Step 3 — Connect Phantom Engine / Enterprise (optional)

Free Optics needs **no account and no API key**. Local `vantio prove`,
`vantio search`, `vantio tail`, `vantio diff`, and `vantio discover --local`
work immediately after a run.

To attach **Phantom Engine** enforcement or an Enterprise on-prem control plane (Gate is not a separate current SKU):

1. Request a trial via [hello@vantio.ai](mailto:hello@vantio.ai) (or complete Stripe
   Checkout once self-serve billing is live — eng-shipped, keys not yet public).
2. You receive an API key (email / SE handoff). There is **no public self-serve
   key dashboard** today — [vantio.ai/dashboard](https://vantio.ai/dashboard)
   redirects to docs.
3. Save the key:

```bash
vantio login
```

Paste your key when prompted (or pass it directly: `vantio login vk_live_xxx`). Vantio
validates it and saves it to `~/.vantio/config.json` (chmod 600) — **no environment
variables to manage.** Every `vantio run` after this automatically picks up the saved
key:

```bash
vantio run node agent.js
```

Check your connection status anytime:

```bash
vantio whoami
# Key:    vk_live…a3f2
# Server: <your Phantom Engine enforce-plane URL>
# Status: connected
```

To disconnect: `vantio logout`.

> **Honesty note:** Remote dashboard sync and fleet `vantio discover` (without
> `--local`) require a Phantom Engine or Enterprise key pointed at a live control plane.
> Free Optics stays fully useful offline. Upgrade path:
> [vantio.ai/pricing](https://vantio.ai/pricing).
> The CLI may still print a technical `pro` tier from the enforce-plane API; that is not a current SKU.

---

## Commands

```bash
vantio login [key]    # save & validate your API key (prompts if omitted; input masked on a TTY)
vantio logout         # remove the stored key
vantio whoami         # show the stored key (masked) + live connection status
vantio run <program>  # spawn a program under the Vantio execution context
vantio discover       # local wrap history (--local) or paid control-plane discover
vantio prove          # generate an auditor-ready proof artifact from a run log (Free)
vantio search [query] # search local run logs by host, path, action, or free text (Free)
vantio tail           # show the latest calls from a captured run (Free)
vantio diff <a> <b>   # compare two local runs — hosts, counts, bytes (Free)
```

`login` refuses to save a key the server rejects (HTTP 401). The full key is never printed — `whoami` and login output only ever show a masked form like `vk_liv…a1b2`.

---

## Usage

```bash
vantio run node agent.js
vantio run tsx agent.ts
```

Wrap a Node process with `vantio run`. The CLI intercepts outbound calls to known LLM APIs via Node `fetch`, `undici.fetch`, `undici.request` (including `Client` / `Pool` / `Agent` `.request()`), `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade`, Node `http`/`https`, Node `http2.connect` / `session.request`, Node `net`/`tls` connect to in-scope hosts, and outbound bytes after `undici.upgrade` / CONNECT, and records connection metadata locally (and to the Phantom Engine enforce plane when a key is configured).

Python is not wrapped by this interceptor. Install [`vantio-agent-sdk`](https://pypi.org/project/vantio-agent-sdk) on that interpreter first, then:

```bash
pip install vantio-agent-sdk
vantio run python agent.py
```

With the SDK installed, `vantio run python` injects the wrap (`sitecustomize` on `PYTHONPATH`) so you do not have to edit the script. Without the SDK, the prefix does not intercept. `shield()` is the in-process alternative when you want a trace id inside the process.

Your code doesn't change. Your agent runs normally. If you've run `vantio login`, the stored key is injected into the child process; an explicit `VANTIO_API_KEY` in your environment always takes precedence.

---

## Flags

```bash
vantio run --audit node agent.js     # flag events as VANTIO_AUDIT_MODE=1
vantio run --summary node agent.js   # print a run summary on exit
```

**`--audit`** — sets `VANTIO_AUDIT_MODE=1` in the child environment, which marks events as audit mode in the enforce-plane ingest payload. Has no observable local effect in Optics-only (free) mode; the flag is passed through to the interceptor for paid enforce-plane correlation.

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

## vantio search / tail / diff — Inspect without a dashboard (Free)

```bash
vantio search openai                   # free-text search across local runs
vantio search --host=api.anthropic.com
vantio tail                            # latest calls from the most recent run
vantio tail -n 50 --run=<trace-id>
vantio diff <run-a> <run-b>            # hosts added/removed, call and byte deltas
```

Same `~/.vantio/runs/` logs as `vantio prove`. Metadata only — never prompts or completions. No API key required.

---

## vantio discover — local wrap history on this machine

```bash
vantio discover --local
vantio discover --local --since=7d --json
```

`--local` reads `~/.vantio/runs` on this machine. That is only processes started with `vantio run` (Node) or `vantio run python` after `pip install vantio-agent-sdk`. It is this machine only — not a fleet inventory and not a scan of every process. curl, browsers, skipped wraps, and forks stay outside this list.

Without `--local` the CLI asks a paid control-plane discover API. If that API is missing, the CLI says so. Optics does not claim it found every agent on the host.

**Options:**

| Flag | Description |
|---|—|
| `--since=<period>` | Look back `24h`, `7d`, or `30d` (default: `24h`) |
| `--host=<hostname>` | Filter to a specific target host |
| `--json` | Output raw JSON instead of a formatted table |
| `--local` | Local wrap logs only — no API key required |

Run `vantio discover --help` for the same bounds.

---

## Enforcement (Phantom Engine)

With a Phantom Engine `VANTIO_API_KEY`, the interceptor fetches policy from the enforce-plane control plane ([`vantio-pro`](https://github.com/vantioai/vantio-pro); Gate is not a separate current SKU) and enforces it locally in your process. A few semantics worth knowing:

- **Host scope** — policy applies to known LLM hosts plus any host named in `blocked_hosts`/`allowed_hosts`. `blocked_hosts` blocks **any** matching host (LLM or not); a non-empty `allowed_hosts` blocks any in-scope host not on the list. Unrelated traffic (OS, package managers, etc.) is never touched.
- **Spend cap** — the USD spend cap is **best-effort and per-process**. Bytes are estimated (request + response, including streamed responses counted after the fact), so the cap gates *subsequent* calls once the running total is crossed rather than aborting a call mid-stream, and it does not aggregate across processes.

---

## Environment variables

| Variable | Description |
|---|—|
| `VANTIO_API_KEY` | Enforce-plane API key from a trial (`hello@vantio.ai`) or Stripe once live — `/dashboard` redirects to docs |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_TELEMETRY` | Set to `1` to opt **in** to usage telemetry (disabled by default) |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to explicitly disable telemetry (overrides `VANTIO_TELEMETRY=1`) |
| `DO_NOT_TRACK` | Set to `1` to disable telemetry (overrides `VANTIO_TELEMETRY=1`) |

---

## Usage telemetry

**Disabled by default.** Vantio does not transmit any usage data unless you explicitly opt in.

To opt in:

```bash
VANTIO_TELEMETRY=1 vantio run node agent.js
```

To opt back out (overrides a system-wide opt-in):

```bash
VANTIO_TELEMETRY_DISABLED=1 vantio run node agent.js
# or
DO_NOT_TRACK=1 vantio run node agent.js
```

**What is sent (only when opted in):**

| Field | Value |
|---|—|
| `anonymousId` | Random UUID stored locally at `~/.vantio/telemetry-id` (0600). Persists across runs. |
| `event` | `"run"` (fired on the first intercepted LLM call in a run) |
| `hosts` | LLM hostnames contacted (e.g. `["api.openai.com"]`) — at most 50 |
| `callCount` | Number of intercepted calls at the time of the ping |
| `runtime` | `"node"` |
| `runtimeVersion` | Node.js version string |
| `os` | `process.platform` (e.g. `"linux"`) |
| `cliVersion` | `@vantio/cli` version |

**Destination:** `POST https://vantio.ai/api/v1/telemetry`

**Trigger:** First intercepted LLM call in a `vantio run` session (not on install, help, version, zero-call runs, or login failures).

**Never sent:** prompts, completions, request/response bodies, API keys, environment variables, source code, internal paths, user content, or any PII.

**Retention:** Unknown. Contact [hello@vantio.ai](mailto:hello@vantio.ai) for the data retention policy.

**Note:** The `anonymousId` field name in the wire format is retained for server compatibility. The local identifier file is `~/.vantio/telemetry-id`.

---

## Supported runtimes

Auto-intercepts LLM calls when running **Node.js** processes (`node`, `tsx`, `ts-node`, `npx`) — Node `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade` (including tunnel bytes after upgrade), Node `http`/`https` including `ClientRequest`, Node `http2`, Node `net`/`tls`, `WebSocket` (host-block and outbound frame size), and Node-spawned `curl` and `wget` (including `env` / `timeout` / `nice`, `curl -K` `url=`, `curl -F` size from stat, stdin size when stdin is a file, `wget -i` URL lists, `sh -c`, file-body size from `--post-file` / `@file`, and PII rewrite of inline argv bodies). Spawned httpie shares host-block and inline `--raw` / field redaction; aria2c shares host-block from argv URLs. Current npm release: **`@vantio/cli` 0.3.20**.

Python, Ruby, and other runtimes are spawned without this Node interceptor. For Python, install the [Python SDK](https://pypi.org/project/vantio-agent-sdk) (`vantio-agent-sdk`) and then `vantio run python agent.py` or `shield()` — urllib / http.client / requests / httpx / aiohttp / urllib3 / pycurl / socket.connect / subprocess curl and wget.

---

## Supported LLM providers

OpenAI (including regional), Anthropic, Google Gemini, Azure OpenAI, Azure AI, Cohere, Mistral, Groq, Together AI, Perplexity, xAI, DeepSeek, Fireworks, OpenRouter, Cerebras, Voyage AI, SambaNova, DeepInfra, Amazon Bedrock, Google Vertex AI, Hugging Face Inference, Replicate, Ollama, hosted NVIDIA NIM.

Browser paths stay outside this wrap. Phantom Engine is runtime protection on enrolled Linux when you need control beneath the app wrap.

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
