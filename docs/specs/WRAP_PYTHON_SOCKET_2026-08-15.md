# Spec — Wrap Python socket (SDK 3.0.5)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run python`) · SDK · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Node CLI stays **0.3.9**.

## Goal

Python `socket.socket.connect` / `socket.create_connection` / `ssl.SSLSocket.connect` to in-scope LLM hosts share host-block and observe with urllib. A raw TCP connect to a blocked host never opens. urllib / requests / httpx / aiohttp must not ingest twice.

This does **not** redact TLS payloads. Curl and browsers stay residual.

## Checklist

- [x] Context / thread flag marks HTTP orig calls so inner `socket.connect` passes through
- [x] Raw `socket.connect` / `create_connection` to in-scope hosts: observe or `BLOCKED_HOST`
- [x] Unix-socket paths pass through
- [x] Control-plane host+port (Gate ingest) passes through
- [x] Policy `allowed_hosts` / `blocked_hosts` count as in-scope (same as Node)
- [x] Tests: raw socket blocked never TCP; urllib block still one run-log event
- [x] No new Mission Control copy

## Out of scope

curl · browsers · WebSocket frames · Stripe · stranger-host · TLS payload redaction
