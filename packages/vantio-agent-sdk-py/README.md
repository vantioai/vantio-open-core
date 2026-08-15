# vantio-agent-sdk · Vantio Optics (Python)

> Vantio Optics open-core SDK for Sight Loop observe — `shield()` telemetry for Python agents. Metadata only; no prompts.

```bash
pip install vantio-agent-sdk
```

Optics: [vantio.ai/optics](https://vantio.ai/optics)

## v3.0.x — Breaking change from v2.x

v3.0.0+ is a complete rewrite. The old `VantioSession` / `VANTIO_PROXY_ENDPOINT` API is removed.
The new API uses `@shield` (a decorator or async context manager) with zero dependencies and no proxy — observe runs inside your SDK, not through an external endpoint.

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

---

## shield() — trace context

```python
from vantio import shield, report_anomaly

# Decorator form
@shield
async def run_agent():
    result = await call_openai(prompt)
    return result

# Context manager form
async with shield() as ctx:
    print(f"Trace ID: {ctx.trace_id}")
    result = await run_agent()
```

### get_current_trace_id()

Returns the active trace ID for the current async context, or `None` outside a `shield()` frame.

```python
from vantio import shield, get_current_trace_id

async with shield() as ctx:
    trace_id = get_current_trace_id()  # same as ctx.trace_id

get_current_trace_id()  # None — outside shield() frame
```

---

## fetch_policy() — policy retrieval

Fetches your tenant's governance policy from `GET /api/v1/config`. Fails open — if the
control plane is unreachable, a permissive default policy is returned so your agent never
stalls waiting for governance.

```python
from vantio import fetch_policy, redact_pii
import os

policy = fetch_policy(os.environ["VANTIO_API_KEY"])

# Check enforcement flags
if policy.enforce:
    if "api.openai.com" in policy.blocked_hosts:
        raise RuntimeError("OpenAI is blocked by policy")

# Use with redact_pii for SDK-side PII scrubbing
if policy.pii_redact:
    result = redact_pii(user_input, policy.pii_types)
    prompt = result.text   # PII scrubbed before the LLM call
```

`VantioPolicy` fields:

| Field | Type | Description |
|-------|------|-------------|
| `enforce` | `bool` | Master switch — when `False`, calls are observed but never blocked/redacted |
| `pii_redact` | `bool` | Whether to redact PII from requests |
| `pii_types` | `list[str]` | PII categories to redact (`"ssn"`, `"email"`, `"credit_card"`, `"phone"`) |
| `allowed_hosts` | `list[str]` | Allow-list of LLM hosts; empty = all known hosts allowed |
| `blocked_hosts` | `list[str]` | Deny-list of LLM hosts |
| `max_request_bytes` | `int` | Hard cap on outbound request size; `0` = no limit |
| `spend_cap_usd` | `float` | Soft USD spend cap; `0` = no cap |

---

## redact_pii() — local PII scrubbing

Pure, side-effect-free local PII redaction using the same patterns as the CLI interceptor
and `@vantio/agent-sdk`. No content leaves the process.

```python
from vantio import redact_pii

result = redact_pii("Contact bob@example.com or call 555-123-4567")
# result.text       → "Contact [VANTIO_REDACTED:EMAIL] or call [VANTIO_REDACTED:PHONE]"
# result.redactions → ["email", "phone"]
```

Pass a custom `pii_types` list to control which categories are scanned (values are
case-insensitive):

```python
result = redact_pii(text, pii_types=["email", "ssn"])
```

Built-in categories: `ssn`, `email`, `credit_card`, `phone`.

`RedactionResult` fields:

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Input string with PII replaced by `[VANTIO_REDACTED:LABEL]` tokens |
| `redactions` | `list[str]` | Category name per matched span (one entry per replacement) |

---

## report_anomaly() — cloud ingest

```python
async with shield():
    await run_agent()
    await report_anomaly(
        target_host="api.openai.com",
        bytes_severed=14382,
        # Valid values: "OBSERVED" | "ALLOWED" | "REDACTED" | "BLOCKED_HOST" | "BLOCKED_SIZE" | "BLOCKED_SPEND"
        action_taken="BLOCKED_HOST",
    )
```

`report_anomaly()` must be called within a `shield()` context. It is a no-op unless
`VANTIO_CLOUD_INGEST=true`. Non-fatal — never crashes the agent.

---

## Environment variables

| Variable | Description |
|---|---|
| `VANTIO_API_KEY` | Your API key from [vantio.ai/dashboard](https://vantio.ai/dashboard) |
| `VANTIO_INGEST_URL` | Ingest endpoint (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to enable cloud routing — `report_anomaly()` is a no-op without this |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to opt out of anonymous usage telemetry |
| `DO_NOT_TRACK` | Set to `1` to opt out of anonymous usage telemetry |

---

## Anonymous telemetry (opt-out)

The SDK sends a single **anonymous** usage ping per process the first time `shield()` runs.
It contains only aggregate, non-identifying metadata — a random anonymous id, the Python
version, the OS string, and an event name. It **never** sends prompts, completions, API
keys, emails, or any content/PII. Fire-and-forget on a daemon thread; never blocks.

```bash
export VANTIO_TELEMETRY_DISABLED=1   # or
export DO_NOT_TRACK=1
```

---

## Zero required dependencies

Core tracing requires only the Python standard library (`contextvars`, `asyncio`, `hashlib`,
`hmac`, `re`). Cloud ingest and anonymous telemetry use `urllib.request` and `threading`.
This package does not depend on aiohttp, requests, or httpx.

While `shield()` is active, Optics records urllib calls to in-scope LLM hosts (OpenAI,
Anthropic, Bedrock, Vertex AI, Hugging Face Inference, Replicate, Ollama, NVIDIA NIM, and
the rest of the catalog). If `requests` or `httpx` are already installed in the agent
environment, `shield()` records those the same way. They are optional; installing this
package does not pull them in. curl and raw sockets stay outside this wrap.
