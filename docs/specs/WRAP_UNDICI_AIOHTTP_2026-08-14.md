# Spec — Wrap completeness follow-on (undici.fetch · aiohttp)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · Python SDK · vantio.ai

Stripe live checkout and a second host stay parked. Same wrap mandate as 3.0.3.

## Goal

`undici.fetch` and Python `aiohttp` share the Optics/Gate path already used by Node `fetch`/`http`/`https` and Python urllib/requests/httpx.

## Checklist

- [x] `undici.fetch` (late `require("undici")` included) uses wrapFetch
- [x] `aiohttp.ClientSession` observe + Gate when installed
- [x] Tests
- [ ] Publish `@vantio/cli` 0.3.4 and `vantio-agent-sdk` 3.0.4
- [ ] Public copy

## Out of scope

curl · raw sockets · browser · `undici.request` / `Client` · HTTP/2 · Stripe · stranger-host
