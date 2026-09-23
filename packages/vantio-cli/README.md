# @vantio/cli

[![npm](https://img.shields.io/npm/v/@vantio/cli.svg)](https://www.npmjs.com/package/@vantio/cli)

> **Vantio Optics | Free Observability for AI Agents**
>
> Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.
>
> Current local candidate: **0.3.21** (remediation branch; not yet published). Python support requires `vantio-agent-sdk`. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state.

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

Local `vantio prove`, `vantio search`, `vantio tail`, `vantio diff`, and `vantio discover` read `~/.vantio/runs` on this machine after a run.

---

## Commands

```bash
vantio run <program>  # spawn a program under the Vantio execution context
vantio discover       # local wrap history on this machine
vantio prove          # generate a proof artifact from a local run log
vantio search [query] # search local run logs by host, path, action, or free text
vantio tail           # show the latest calls from a captured run
vantio diff <a> <b>   # compare two local runs — hosts, counts, bytes
```

---

## Usage

```bash
vantio run node agent.js
vantio run tsx agent.ts
```

Wrap a Node process with `vantio run`. The CLI intercepts outbound calls to known LLM APIs via Node `fetch`, `undici.fetch`, `undici.request` (including `Client` / `Pool` / `Agent` `.request()`), `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade`, Node `http`/`https`, Node `http2.connect` / `session.request`, Node `net`/`tls` connect to in-scope hosts, and outbound bytes after `undici.upgrade` / CONNECT, and records connection metadata locally.

Python is not wrapped by this interceptor. Install [`vantio-agent-sdk`](https://pypi.org/project/vantio-agent-sdk) on that interpreter first, then:

```bash
pip install vantio-agent-sdk
vantio run python agent.py
```

With the SDK installed, `vantio run python` injects the wrap (`sitecustomize` on `PYTHONPATH`) so you do not have to edit the script. Without the SDK, the prefix does not intercept. `shield()` is the in-process alternative when you want a trace id inside the process.

Your code doesn't change. Your agent runs normally. Observed calls are recorded on this machine.

---

## Flags

```bash
vantio run --summary node agent.js   # print a run summary on exit
```

**`--summary`** — prints a summary when the process exits:

```
[ ∅ VANTIO ] Run Summary
  LLM calls:    7
  Hosts:        api.openai.com, api.anthropic.com
  Total bytes:  94,201
  Duration:     12.4s
  → Run `vantio prove` to export an auditor-ready artifact from this run.
```

Intercepted calls print to the terminal in real time.

---

## vantio prove — proof artifacts

```bash
vantio prove                           # HTML report — most recent run
vantio prove --list                    # list all local run logs
vantio prove --run=<trace-id>          # report for a specific run
vantio prove --format=md               # Markdown to stdout
vantio prove --format=html --out=proof.html
```

`vantio prove` reads the run logs that `vantio run` automatically writes to
`~/.vantio/runs/` and generates a self-contained proof document. Reports include
trace IDs, process IDs, byte counts, host breakdown, and action labels.

Prompts and completions are never stored.

---

## vantio search / tail / diff

```bash
vantio search openai                   # free-text search across local runs
vantio search --host=api.anthropic.com
vantio tail                            # latest calls from the most recent run
vantio tail -n 50 --run=<trace-id>
vantio diff <run-a> <run-b>            # hosts added/removed, call and byte deltas
```

Same `~/.vantio/runs/` logs as `vantio prove`. Metadata only — prompts and completions are never stored.

---

## vantio discover — local wrap history on this machine

```bash
vantio discover --local
vantio discover --local --since=7d --json
```

`vantio discover` reads `~/.vantio/runs` on this machine. That is only processes started with `vantio run` (Node) or `vantio run python` after `pip install vantio-agent-sdk`. It is this machine only — not a fleet inventory and not a scan of every process. curl, browsers, skipped wraps, and forks stay outside this list. `--local` is accepted and does not change that behavior.

**Options:**

| Flag | Description |
|---|—|
| `--since=<period>` | Look back `24h`, `7d`, or `30d` (default: `24h`) |
| `--host=<hostname>` | Filter to a specific target host |
| `--json` | Output raw JSON instead of a formatted table |
| `--local` | Accepted. Discover is always local run logs |

Run `vantio discover --help` for the same bounds.

---

## Environment variables

| Variable | Description |
|---|---|
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

**Trigger:** First intercepted LLM call in a `vantio run` session (not on install, help, version, or zero-call runs).

**Never sent:** prompts, completions, request/response bodies, API keys, environment variables, source code, internal paths, user content, or any PII.

**Retention:** Unknown. Contact [hello@vantio.ai](mailto:hello@vantio.ai) for the data retention policy.

**Note:** The `anonymousId` field name in the wire format is retained for server compatibility. The local identifier file is `~/.vantio/telemetry-id`.

---

## Supported runtimes

Auto-intercepts LLM calls when running **Node.js** processes (`node`, `tsx`, `ts-node`, `npx`) — Node `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade` (including tunnel bytes after upgrade), Node `http`/`https` including `ClientRequest`, Node `http2`, Node `net`/`tls`, `WebSocket` outbound frame size, and Node-spawned `curl` and `wget` (including `env` / `timeout` / `nice`, `curl -K` `url=`, `curl -F` size from stat, stdin size when stdin is a file, `wget -i` URL lists, `sh -c`, and file-body size from `--post-file` / `@file`). Spawned httpie and aria2c argv URLs are included in the same local record. Current npm release: **`@vantio/cli` 0.3.20**.

Python, Ruby, and other runtimes are spawned without this Node interceptor. For Python, install the [Python SDK](https://pypi.org/project/vantio-agent-sdk) (`vantio-agent-sdk`) and then `vantio run python agent.py` or `shield()` — urllib / http.client / requests / httpx / aiohttp / urllib3 / pycurl / socket.connect / subprocess curl and wget.

---

## Supported LLM providers

OpenAI (including regional), Anthropic, Google Gemini, Azure OpenAI, Azure AI, Cohere, Mistral, Groq, Together AI, Perplexity, xAI, DeepSeek, Fireworks, OpenRouter, Cerebras, Voyage AI, SambaNova, DeepInfra, Amazon Bedrock, Google Vertex AI, Hugging Face Inference, Replicate, Ollama, hosted NVIDIA NIM.

Browser paths stay outside this wrap.

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

[vantio.ai](https://vantio.ai) · [Optics](https://vantio.ai/optics) · MIT License
