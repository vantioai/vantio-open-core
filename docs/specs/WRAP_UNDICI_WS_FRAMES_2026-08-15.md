# Spec — Wrap WebSocket / tunnel frames after undici.upgrade (CLI 0.3.10)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.5**.

## Goal

After a successful `undici.upgrade` or HTTP CONNECT tunnel to an in-scope host, outbound bytes on the returned socket share observe and Gate size/spend caps with HTTP. Host-block still happens before the tunnel opens (0.3.7).

This does **not** parse or redact frame payloads (that would read the conversation). Curl and browsers stay residual.

## Checklist

- [x] Wrap `handler.onUpgrade` socket `write` / `end` for in-scope upgrade and CONNECT
- [x] First payload write: ingest OBSERVED / ALLOWED with `bytes_observed` (`undici_ws`)
- [x] `max_request_bytes` / spend cap can stop further writes (`BLOCKED_SIZE` / `BLOCKED_SPEND`)
- [x] Existing `undici.upgrade` host-block still never opens the tunnel
- [x] Regular fetch still one ingest event (not a second `undici_ws` event)
- [x] No new Mission Control copy

## Out of scope

curl · browsers · Stripe · stranger-host · TLS / WebSocket payload redaction
