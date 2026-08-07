# Sight Loop — Vantio Optics workflow

**Vantio Optics** (Free · Open Core) ships one proprietary workflow: **Sight Loop** — wrap, capture, inspect, and honestly surface residual risk. No policy enforcement, no Phantom Engine claims — observe only.

```
Wrap → Capture → Inspect / export → Residual (upgrade cue)
```

---

## Step 1 — Wrap your agent

Start every agent run under Optics. No code changes for Node.js agents:

```bash
npm install -g @vantio/cli
vantio run node agent.js
```

Python agents use the SDK decorator instead of `vantio run`:

```bash
pip install vantio-agent-sdk
```

```python
from vantio import shield

@shield
async def run_agent():
    ...
```

**What wrapping does:** injects the Open Core interceptor (`NODE_OPTIONS --require` for Node) so outbound LLM HTTP calls are visible without routing traffic through a proxy.

No API key required. Optics works immediately in **observe-only** mode.

---

## Step 2 — Capture a developer data log (never content)

Optics exists to give you a useful egress dataset — not to babysit the agent. Each intercepted call records (schema_version **2**):

| Field | Example | Why you need it |
|-------|---------|-----------------|
| Host | `api.openai.com` | Where the agent went |
| Provider | `openai` | Group spend/debug by vendor |
| Method + path | `POST /v1/chat/completions` | Which API surface (query string stripped — may contain keys) |
| Status / ok | `200` / `true` | Failures without reading bodies |
| Duration ms | `842` | Latency per call |
| Request bytes | `1204` | Size of outbound payload (length only) |
| Response bytes | `4,821` | Volume when `Content-Length` is present |
| Content-Type | `application/json` | Response shape hint |
| Process / PID / Node / platform | runtime facts | Which process, which environment |
| Trace ID | `0x1a2b3c4d5e6f7a8b` | Correlate the whole run |
| Timestamp | ISO-8601 | Ordering and audits |
| Error class | `TypeError` / `network_error` | Failed fetches still land in your log |
| Summary `by_host` / `by_provider` | rollups | Quick triage without a dashboard |

**Never captured:** prompts, completions, request/response bodies, Authorization headers, or query strings.

Free-tier action label: **`OBSERVED`**. Optics does not block, redact, or cap — those belong to **Vantio Gate** (Pro).

Terminal output on each call:

```
[ ∅ VANTIO ] Outbound LLM call intercepted
  host:     api.openai.com
  provider: openai
  method:   POST /v1/chat/completions
  status:   200
  duration: 842ms
  bytes:    4,821
  pid:      12345
  time:     2026-07-16T18:00:01.100Z
```

On exit, run logs are written locally to `~/.vantio/runs/<trace-id>.json` (mode `0600`) — **your** data log on disk.

---

## Step 3 — Inspect and export

**Local history (Free):**

```bash
vantio discover --local          # runs on this machine, no dashboard sync
vantio prove                     # HTML proof from the most recent run
vantio prove --list              # all local run logs
vantio prove --format=md         # Markdown for auditors / CI artifacts
```

See [prove.md](./prove.md) for the full `vantio prove` reference.

**Optics MCP (agent hosts / IDEs):** `@vantio/optics-mcp` exposes the same observe surface as MCP tools (`optics_list_runs`, `optics_get_run`, `optics_prove`, `optics_discover_local`, `optics_upgrade_path`). Read-only — when agents need enforce, they follow the upgrade path to Gate. See [optics-mcp.md](./optics-mcp.md).

**Explain what happened:** proof artifacts include trace ID, machine, PID, per-host byte counts, and action badges — enough to answer “which LLM endpoints did this agent hit, when, and from which process?” without exposing content.

---

## Step 4 — Honest residual → upgrade cue

Optics is **blind by design, not a proxy** — and **bypassable by design**:

- Processes not started with `vantio run` (or without the Python `@shield`) stay silent
- Native socket calls that skip `fetch` are not observed
- Ungoverned paths do not appear in your timeline

That gap is intentional. It is the honest sell-up:

| Residual | Closes with |
|----------|-------------|
| No block / redact / cap | **Vantio Gate** (Pro) — Policy Latch |
| App-layer bypass (sockets, unenrolled processes) | **Vantio Phantom Engine** (Enterprise) — Rogue Reconciliation |

Run `vantio discover --local` to see what Optics actually observed on your machine. Compare that to what you *know* your stack calls — the delta is residual risk.

> Optics accepts: **no block**, and **ungoverned paths stay silent**.  
> Pro sells enforce; Enterprise sells proof when enforce was skipped.

Full fence: [observe-only.md](./observe-only.md)

---

## Offline prove path (no network, no API key)

Verify the full Sight Loop without hitting real LLM endpoints:

```bash
./scripts/sight-loop-prove.sh
```

The script spins up a local mock LLM host, runs wrap → capture → `vantio prove`, and prints a Markdown proof artifact. Useful for CI smoke checks and first-run trust.

---

## See also

- [Getting started](./getting-started-tier01.md) — 60-second quickstart
- [Observe only — no enforce](./observe-only.md) — Free-tier fence
- [Framework integrations](./framework-integrations.md) — LangChain, OpenAI SDK, etc.
- [Prove artifacts](./prove.md) — auditor-ready export

*[vantio.ai](https://vantio.ai) · [Pricing](https://vantio.ai/pricing)*
