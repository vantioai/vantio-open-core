# vantio-agent-sdk · Python

> Zero-line AI governance telemetry for Python agents. pip install, decorate, done.

```bash
pip install vantio-agent-sdk
```

## v3.0.0 — Breaking change from v2.x

v3.0.0 is a complete rewrite. The old `VantioSession` / `VANTIO_PROXY_ENDPOINT` API is removed.
The new API uses `@shield` (a decorator or async context manager) with zero dependencies and no proxy — governance runs inside your SDK, not through an external endpoint.

**Migrate from v2.x:**
```python
# Old (v2.x) — remove this
from vantio.session import VantioSession
with VantioSession(agent_name="my-agent") as session: ...

# New (v3.x) — use this instead
from vantio import shield
@shield
async def run_agent(): ...
# or: async with shield() as ctx: ...
```

## Usage

```python
from vantio import shield, report_anomaly

# Decorator form
@shield
async def run_agent():
    result = await call_openai(prompt)
    return result

# Context manager form
async with shield() as trace:
    print(f"Trace ID: {trace.trace_id}")
    result = await run_agent()

# Report anomaly
async with shield():
    await run_agent()
    await report_anomaly(
        target_host="api.openai.com",
        bytes_severed=14382,
        # Valid values: "OBSERVED" | "ALLOWED" | "REDACTED" | "BLOCKED_HOST" | "BLOCKED_SIZE" | "BLOCKED_SPEND"
        action_taken="BLOCKED_HOST",
    )
```

## get_current_trace_id()

Returns the active trace ID for the current async context, or `None` outside a `shield()` frame.

```python
from vantio import shield, get_current_trace_id

async with shield() as ctx:
    trace_id = get_current_trace_id()  # same as ctx.trace_id
    print(f"Trace: {trace_id}")

get_current_trace_id()  # None — outside shield() frame
```

## Environment Variables

| Variable | Description |
|---|---|
| `VANTIO_API_KEY` | Your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard) |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to enable cloud routing — `report_anomaly()` is a no-op without this |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode |

## Anonymous telemetry (opt-out)

The SDK sends a single **anonymous** usage ping per process the first time `shield()` runs. It contains only aggregate, non-identifying metadata — a random anonymous id (stored at `~/.vantio/telemetry-id`), the Python version, the OS string, and an event name. It **never** sends prompts, completions, API keys, emails, or any content/PII. The request is fire-and-forget on a short-timeout daemon thread, so it can never block or crash your agent.

Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

## Zero dependencies

Core tracing requires only the Python standard library (`contextvars`, `asyncio`, `hashlib`, `hmac`). Cloud ingest and anonymous telemetry use `urllib.request` and `threading`. No aiohttp, no httpx, no requests.
