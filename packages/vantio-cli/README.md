# @vantio/cli

[![npm](https://img.shields.io/npm/v/@vantio/cli.svg)](https://www.npmjs.com/package/@vantio/cli)

> **Vantio Optics | Free Observability for AI Agents**
>
> Free, local-first observability for supported AI-agent traffic. Prompts and completions are never stored.
>
> The running version is `vantio --version`. Python support requires `vantio-agent-sdk`. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state.

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
vantio demo           # in-process demo of one observed call (no network)
vantio status         # local install and data status (no network by default)
vantio discover       # local wrap history on this machine
vantio prove          # generate a proof artifact from a local run log
vantio search [query] # search local run logs by host, path, action, or free text
vantio tail           # show the latest calls from a captured run
vantio diff <a> <b>   # compare two local runs — hosts, counts, bytes
vantio coverage       # processes and connections on this system, and which paths are on the allowlist
vantio destinations   # flag a destination the first time a program connects to it
vantio export         # send recorded events to OTLP/HTTP JSON, syslog or JSON lines, or a webhook
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

`vantio run` writes a run record for every command, including commands that are not `node`, `npx`, `tsx`, or `ts-node`. On Linux it reads `/proc` while that process and the processes it starts are alive, and records the process tree and the outbound sockets it sees. A socket is attributed to the process that held it, and that process is listed on `vantio coverage`. For a command that is not Node or Python, the first sampled socket to a destination prints a New destination line while the command is still running. Node and Python print that line when the supported call starts, before the response returns. The read does not change the process and does not query DNS. A socket that opens and closes between samples can be missed. Those records are included in `vantio coverage` and `vantio destinations`.

---

## Flags

```bash
vantio run --summary node agent.js   # print a run summary on exit
vantio run --json node agent.js      # unstable JSON run record on stdout
vantio run --mcp-enforce node agent.js
```

`vantio run` loads in-process MCP awareness for Node, and the same library for Python child-process stdio. The default is observe, and injection and rug-pull stay on log. `--mcp-enforce` withholds inside that process. `VANTIO_MCP_AWARENESS=off` does not load it. The path does not add a proxy process. Payload text is not stored. This is not Phantom Engine. Host attachment remains a later step.

**`--json`** on `run`, `demo`, `status`, `discover`, `prove`, `search`, `tail`, `diff`, `coverage`, `destinations`, and `export` prints `"schema_status": "unstable-pre-1.0"`. That shape may change without notice. Field mapping to OpenTelemetry GenAI terms is documented in the open-core repo at `docs/optics-otel-mapping.md`. `vantio export --otlp` sends OTLP/HTTP JSON. `vantio export --otlp-grpc` sends the same fields as unary OTLP/gRPC over HTTP/2. Optics does not start a collector.

**`--summary`** — prints a summary when the process exits:

```
[ ∅ VANTIO ] Run Summary
  LLM calls:    7
  Hosts:        api.openai.com, api.anthropic.com
  Total bytes:  94,201
  Duration:     12.4s
  → Run `vantio prove` to export a local proof artifact from this run.
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
vantio tail -n 0                       # zero calls
vantio tail --all                      # every call in the run
vantio diff <run-a> <run-b>            # hosts added/removed, call and byte deltas
```

`vantio tail --json --follow` is a usage error. Proofs and search results separate **Optics status** from **Application outcome**. The HTTP code is shown as HTTP status. A stored `ok` flag is not used.

```bash
vantio demo                            # POST /v1/chat/completions, HTTP 200, no network
vantio status                          # version, telemetry, local data, provider SDKs
vantio status --check-registry         # also asks npm for the latest version
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

## Coverage map

```bash
vantio coverage
vantio coverage --json
vantio coverage --since=7d --allowlist=./allowlist.json
```

`vantio coverage` reads run logs and `mcp-observations.jsonl` on this system. It prints every recorded process and connection, then splits paths into two lists:

- **Under authority** — the destination or MCP tool name is on the allowlist.
- **Outside authority** — it was seen, and it is not on that list.

The text view and `--json` are the same map. JSON uses `schema` `vantio.optics.coverage.v1` and `schema_status` `unstable-pre-1.0`. A curl or wget spawn recorded on a call is shown as that program, from the parent. On Linux, `vantio coverage` also reads `/proc` and the TCP socket tables. A live process outside the wrap is marked **not covered** when its command looks like an AI program and it has a connection, or when `/etc/hosts` names that socket as an in-scope AI host. The read does not change the process and does not query DNS. Browser paths and calls that never hit the interceptor stay named under **Not covered**.

The command reads this system. A record that stored another hostname is listed under that name. It does not connect to other machines. `vantio coverage`, `vantio destinations`, and `vantio export` read `~/.vantio` and, when `VANTIO_HOME` is a different directory, that directory too. `vantio discover`, `search`, `tail`, `diff`, and `prove` still read only `~/.vantio`.

The allowlist and `seen-destinations.json` are stored under `VANTIO_HOME` when that variable is set, otherwise under `~/.vantio`. If `VANTIO_HOME` has no allowlist file, `~/.vantio/allowlist.json` is used when it exists. An explicit `--allowlist` path must exist. A missing default file means nothing is under authority.

```json
{
  "schema": "vantio.optics.allowlist.v1",
  "destinations": ["billing.internal.example", "*.openai.example"],
  "mcp_tools": ["tools/read"],
  "alert_on_allowlist": false
}
```

`*.example.com` matches one DNS label. An entry may be an object with `"alert": true` or `"alert": false`. Prompts and completions are never stored. Query strings are not shown.

---

## New destination

```bash
vantio destinations
vantio destinations --json
vantio destinations --dry-run
```

`vantio destinations` walks local records in time order. The first connection from a program to a destination it has not used is flagged **New destination**, with the program, the destination, and the first connection time. The same pair is not flagged again. `--since` chooses which of those new flags to print. It does not forget a connection that happened before the window. The memory is `seen-destinations.json` in the directory described above. The first full run therefore flags every destination that is not on the allowlist.

A destination on the allowlist is not flagged unless `alert_on_allowlist` is true, or that entry sets `"alert": true`. The flag does not stop the call.

---

## Monitoring export

```bash
vantio export --otlp=http://127.0.0.1:4318
vantio export --jsonl=./optics.jsonl
vantio export --syslog=udp://127.0.0.1:514
vantio export --webhook=https://collector.example/optics
```

`vantio export` sends the recorded events. Use one or more of `--otlp`, `--jsonl`, `--syslog`, and `--webhook`.

- `--otlp` is a base URL. The command POSTs OTLP/HTTP JSON to `/v1/traces`, `/v1/metrics`, and `/v1/logs`. The metric is a gauge, `vantio.optics.bytes`, summed for that batch. It is not a token count. The Optics trace id is attribute `vantio.trace_id`. The OTLP `traceId` is a 32-hex digest of that id, because an Optics trace id is not a W3C trace id.
- `--jsonl` appends one JSON object per line. `-` writes to stdout.
- `--syslog` appends RFC 5424 lines whose message is the same JSON. A file path, `-`, `udp://host:port`, or `tcp://host:port` are accepted.
- `--webhook` POSTs `{"schema":"vantio.optics.export.v1","events":[...]}`.

Plaintext `http` and `grpc` are accepted only for loopback. Other hosts need `https` or `grpcs`. Optics does not start a collector. A one-shot export exits non-zero when a destination does not accept the batch and does not update the seen-destination file. An empty record set prints `No events.` and does not send.

`vantio export --follow` reads `live.jsonl` as events are appended and sends them to the same destinations. A failed send is retried with backoff. While that batch is still waiting, newer lines stay in the journal. The buffer holds at most 1000 events and drops the oldest when it is full. `VANTIO_EXPORT_OTLP`, `VANTIO_EXPORT_OTLP_GRPC`, `VANTIO_EXPORT_JSONL`, `VANTIO_EXPORT_SYSLOG`, and `VANTIO_EXPORT_WEBHOOK` supply those destinations when the matching flag is omitted, so `vantio export --follow` can stay running.

`vantio tail --follow` prints a New destination line when the call happens. The clock time is local `HH:MM:SS`. The line is also written on the wrapped process's stderr at that moment.

`VANTIO_EXPORT_WEBHOOK_TOKEN`, when set, is sent as a bearer token on the webhook only. The CLI does not print it. New-destination flags in the batch follow the same rules as `vantio destinations`.

Prompts, completions, header values, and query strings are not export fields.

---

## Environment variables

| Variable | Description |
|---|---|
| `VANTIO_TELEMETRY` | Set to `1` to opt **in** to usage telemetry (disabled by default) |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to explicitly disable telemetry (overrides `VANTIO_TELEMETRY=1`) |
| `DO_NOT_TRACK` | Set to `1` to disable telemetry (overrides `VANTIO_TELEMETRY=1`) |
| `VANTIO_EXPORT_JSONL` | JSON-lines path used by `vantio export` when `--jsonl` is omitted. |
| `VANTIO_EXPORT_OTLP` | OTLP/HTTP base URL used when `--otlp` is omitted. |
| `VANTIO_EXPORT_OTLP_GRPC` | OTLP/gRPC URL used when `--otlp-grpc` is omitted. |
| `VANTIO_EXPORT_SYSLOG` | Syslog target used when `--syslog` is omitted. |
| `VANTIO_EXPORT_WEBHOOK` | Webhook URL used when `--webhook` is omitted. |
| `VANTIO_EXPORT_WEBHOOK_TOKEN` | Optional bearer token for `vantio export --webhook`. Not printed. |

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
| `callCount` | Completed in-scope calls recorded in this process when the once-per-process ping is sent. The first completed call reports 1. |
| `runtime` | `"node"` |
| `runtimeVersion` | Node.js version string |
| `os` | `process.platform` (e.g. `"linux"`) |
| `cliVersion` | `@vantio/cli` version |

**Destination:** `POST https://vantio.ai/api/v1/telemetry`

**Trigger:** First intercepted LLM call in a `vantio run` session (not on install, help, version, or zero-call runs).

**Never sent:** prompts, completions, request/response bodies, API keys, environment variables, source code, internal paths, user content, or any PII.

Telemetry is disabled by default. Set VANTIO_TELEMETRY=1 to opt in. VANTIO_TELEMETRY_DISABLED=1 or DO_NOT_TRACK=1 override.

**Note:** The `anonymousId` field name in the wire format is retained for server compatibility. The local identifier file is `~/.vantio/telemetry-id`.

---

## Supported runtimes

Auto-intercepts LLM calls when running **Node.js** processes (`node`, `tsx`, `ts-node`, `npx`) — Node `fetch`, `undici.fetch`, `undici.request`, `undici.stream` / `pipeline` / `dispatch` / `connect` / `upgrade` (including tunnel bytes after upgrade), Node `http`/`https` including `ClientRequest`, Node `http2`, Node `net`/`tls`, `WebSocket` outbound frame size, and Node-spawned `curl` and `wget` (including `env` / `timeout` / `nice`, `curl -K` `url=`, `curl -F` size from stat, stdin size when stdin is a file, `wget -i` URL lists, `sh -c`, and file-body size from `--post-file` / `@file`). Spawned httpie and aria2c argv URLs are included in the same local record. The running version is `vantio --version`.

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
