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
        action_taken="POLICY_VIOLATION",
    )
```

## Environment Variables

```bash
VANTIO_API_KEY=vantio_xxxx       # From app.vantio.ai/success
VANTIO_INGEST_URL=https://vantio.ai
VANTIO_CLOUD_INGEST=true          # Enable cloud routing
VANTIO_AUDIT_MODE=1               # Optional: flag as audit mode
```

## Anonymous telemetry (opt-out)

The SDK sends a single **anonymous** usage ping per process the first time `shield()` runs. It contains only aggregate, non-identifying metadata — a random anonymous id (stored at `~/.vantio/telemetry-id`), the Python version, the OS string, and an event name. It **never** sends prompts, completions, API keys, emails, or any content/PII. The request is fire-and-forget on a short-timeout daemon thread, so it can never block or crash your agent.

Opt out at any time:

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

## Zero dependencies

Core tracing requires only the Python standard library (`contextvars`, `asyncio`, `hashlib`, `hmac`). Cloud ingest and anonymous telemetry use `urllib.request` and `threading`. No aiohttp, no httpx, no requests.
