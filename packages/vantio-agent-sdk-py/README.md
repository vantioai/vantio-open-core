# vantio-agent-sdk · Python

> Zero-line AI governance telemetry for Python agents. pip install, decorate, done.

```bash
pip install vantio-agent-sdk
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

## Zero dependencies

Core tracing requires only the Python standard library (`contextvars`, `asyncio`, `hashlib`, `hmac`). Cloud ingest uses `urllib.request`. No aiohttp, no httpx, no requests.
