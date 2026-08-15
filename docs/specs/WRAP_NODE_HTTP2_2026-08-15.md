# Spec — Wrap Node http2 (CLI 0.3.8)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.4**.

## Goal

Node `http2.connect` and `session.request` share host block / redact / size / spend with Node `http`. Blocked sessions never open TCP. Ingest uses the same `action_taken` values Mission Control already displays.

## Checklist

- [x] `http2.connect` host-block before the session opens (`VANTIO_GATE_BLOCKED`)
- [x] `session.request` write/end redact + size + spend
- [x] Policy delay: buffer connect/request until `policyReady` (same as Node http)
- [x] Tests: blocked_hosts never reach the h2c target; redact strips email
- [x] `report()` sets `bytes_observed` so MC KPIs roll up
- [x] No new Mission Control copy or library pills

## Out of scope

curl · raw sockets · browser · WebSocket frames after upgrade · Stripe · stranger-host
