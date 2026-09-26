# vantio-agent-sdk · Vantio Optics (Python)

**Vantio** is the infrastructure control layer for autonomous AI. This package is **Vantio Optics** Observe for Python: record where the agent calls LLM APIs (host, size, process, trace) without storing prompts or completions. Optics is free. Optics does not block, redact, or cap spend on its own.

Optics helps you see. [Phantom Engine](https://vantio.ai/phantom) is runtime protection on enrolled Linux — Observe, Enforce, and Control in one purchase, at $799/node/mo. [Enterprise](https://vantio.ai/enterprise) adds governance when you need proof and process on top — talk to sales. Continuous Assurance is how the suite stays true after install; it is not a separate product.

> **Optics** (Free) · **Phantom Engine** ($799/node/mo) · **Enterprise** (talk to sales)

```bash
pip install vantio-agent-sdk
```

Prefixing `vantio run python` without this SDK does not intercept. Python support requires `vantio-agent-sdk`. Follow the current Python SDK example and verify that a supported outbound event appears before relying on the coverage state.

```bash
pip install vantio-agent-sdk
vantio run python agent.py
```

Optics: [vantio.ai/optics](https://vantio.ai/optics) · Pricing: [vantio.ai/pricing](https://vantio.ai/pricing) · Docs: [vantio.ai/docs](https://vantio.ai/docs)

## 3.1.0 — HTTP outcome and customer lines

A stored HTTP call sets `ok` from the status code. `ok` is true for 200–399 and false for 400–599. A 4xx or 5xx response is the provider's outcome. It is not stored as `network_error`. A refused connection, a DNS failure, or a TLS failure still uses `network_error`, and it has no HTTP status. A wrapped application exception is stored as the exception class name only, with no HTTP status and without `network_error`.

Each recorded call keeps two machine fields and three customer lines:

| Field | Human line | Meaning |
|---|---|---|
| `opticsStatus` | Optics status | Optics completed the observation. A recorded call is `SUCCESS`. |
| `applicationStatus` | Observed outcome | Machine token: `SUCCESS` for 200–399, `APPLICATION_ERROR` for 400–599, or `UNAVAILABLE` when no HTTP status was stored. |
| `applicationOutcomeLabel` | Observed outcome | The specific result, such as `Provider authentication failed` for HTTP 401 or `Provider rate-limited the request` for HTTP 429. |
| `providerResponse` | Provider response | The concrete result, such as `HTTP 401 Unauthorized`. An unknown host uses the heading Upstream response. |

`APPLICATION_ERROR` stays the machine category for an unsuccessful provider response. The customer line is the observed outcome for that status, not a generic error label. The run log names the headings in `status_labels` and sets `schema_status` to `unstable-pre-1.0`. Mixed machine outcomes in one run are `PARTIAL`. The summary line for that run is `Partial`.

When the hostname is in the supported provider catalog, the record names that provider and the destination. Any other host, including an extra host, is an upstream service. Optics does not block, reject, or enforce the provider result.

`http.client` and `pycurl` still do not store an HTTP status on the success path. That outcome stays `UNAVAILABLE`, with the line `Provider outcome unavailable` and the response `No HTTP response`.

A trace with no supported call does not write a run log. The empty view is Optics status `Not observed` and observed outcome `No supported AI call observed`.

Telemetry is unchanged: it stays off unless `VANTIO_TELEMETRY=1`. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` still override that opt-in. Phantom Engine and Enterprise APIs stay separately provisioned. Free Optics still needs no account and no API key.

## 3.0.15 — telemetry wording

Anonymous usage telemetry stays off unless you set `VANTIO_TELEMETRY=1`. The wire payload is unchanged from 3.0.14. Free Optics still needs no account and no API key.

## 3.0.14 — packaging metadata only

This patch corrects PyPI project URLs and long-description product model: Optics (free), Phantom Engine ($799/node/mo — Observe, Enforce, and Control), Enterprise (talk to sales). Does not market any other standalone public SKU. SDK behavior is unchanged from 3.0.13.

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

Scope: this API is part of Vantio Phantom Engine / Enterprise and requires a separately provisioned control-plane key. It is not part of free Vantio Optics, which runs local-first with no account and no API key.

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

Scope: this API is part of Vantio Phantom Engine / Enterprise and requires a separately provisioned control-plane key. It is not part of free Vantio Optics, which runs local-first with no account and no API key.

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

Free Optics runs on this machine with no account and no API key. These three variables only control the optional anonymous ping:

| Variable | Description |
|---|---|
| `VANTIO_TELEMETRY` | Set to `1` to send one anonymous usage ping per process. The ping stays off unless this is set. |
| `VANTIO_TELEMETRY_DISABLED` | Set to `1` to keep the ping off even when `VANTIO_TELEMETRY=1`. |
| `DO_NOT_TRACK` | Set to `1` to keep the ping off even when `VANTIO_TELEMETRY=1`. |

The variables below are for a separately provisioned Phantom Engine or Enterprise control plane. They are not required for free Optics.

| Variable | Description |
|---|---|
| `VANTIO_INGEST_URL` | Control-plane base URL (default: `https://vantio.ai`) |
| `VANTIO_CLOUD_INGEST` | Set to `true` to enable cloud routing. `report_anomaly()` does nothing without this. |
| `VANTIO_AUDIT_MODE` | Set to `1` to flag events as audit mode |

---

## Telemetry

Telemetry is disabled by default. Set `VANTIO_TELEMETRY=1` to opt in. `VANTIO_TELEMETRY_DISABLED=1` or `DO_NOT_TRACK=1` override that opt-in.

The automatic ping runs once per process, on the first `shield()` entry, before HTTP observations are recorded. On that ping, `callCount` is 0 and `hosts` is empty. Calling `shield()` again in the same process does not send a second ping.

When a ping is sent, the body contains `anonymousId`, `runtime`, `runtimeVersion`, `os`, `event`, `hosts`, and `callCount`. `hosts` is a list of LLM hostnames, at most 50. Optional fields, only when a caller sets them, are `sdkVersion`, `redactedCount`, `blockedCount`, and `framework`. The ping does not include prompts, completions, API keys, or email.

---

## What gets captured

The local Optics record stores:

- Which LLM endpoint was called
- Response size in bytes
- Process ID and timestamp
- A trace ID linking calls in the same `shield()` / `vantio run python` wrap

That local record is not the telemetry ping. The ping's fields are listed in the telemetry section above.

Prompts, completions, and request content are never stored.

---

## Zero dependencies

Core tracing requires only the Python standard library (`contextvars`, `asyncio`, `hashlib`,
`hmac`, `re`). Cloud ingest and anonymous telemetry use `urllib.request` and `threading`.
No aiohttp, no httpx, no requests.

MIT License · [vantio.ai/optics](https://vantio.ai/optics) · [vantio.ai/phantom](https://vantio.ai/phantom) · [vantio.ai/enterprise](https://vantio.ai/enterprise) · [vantio.ai/pricing](https://vantio.ai/pricing) · [vantio.ai/docs](https://vantio.ai/docs)
