# Spec — Wrap completeness follow-on (undici.connect · upgrade)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · docs

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.4**.

## Goal

`undici.connect` (HTTP CONNECT tunnels) and `undici.upgrade` (including WebSocket upgrade) share host block / observe with the existing `dispatch` wrap.

CONNECT and upgrade handlers throw if we synthesize a normal HTTP 403 (`onHeaders`). Block by calling `handler.onError` with `VANTIO_GATE_BLOCKED` and **not** calling orig dispatch.

After a successful upgrade, socket frames stay residual (no PII scan on the tunnel). Host block still applies before the tunnel opens.

## Checklist

- [x] CONNECT / upgrade no longer skip Gate in `applyDispatchGate`
- [x] Block path uses `onError`, not fake `onHeaders(403)`
- [x] Tests: `undici.connect` and `undici.upgrade` blocked_hosts never reach the target
- [ ] Publish `@vantio/cli` 0.3.7
- [x] Residual notes drop connect/upgrade from “outside this wrap”

## Out of scope

curl · raw sockets · browser · WebSocket *frames* after upgrade · Node `http2` module · Stripe · stranger-host
