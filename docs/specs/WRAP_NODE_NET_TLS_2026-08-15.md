# Spec — Wrap Node net/tls connect (CLI 0.3.9)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.4**.

## Goal

Node `net.Socket.connect` / `tls.connect` to in-scope LLM hosts share host-block and observe with Node `http`. A raw TCP connect to a blocked host never opens. HTTP, undici, and http2 already on the wrap must not ingest twice.

This does **not** redact or cap TLS bytes (that would be MITM). Curl, browsers, and Python `socket` stay residual.

## Checklist

- [x] `AsyncLocalStorage` marks HTTP/undici/http2 orig calls so inner `Socket.connect` passes through
- [x] Raw `net.connect` / `tls.connect` / `Socket.connect` to in-scope hosts: observe or `BLOCKED_HOST` (`VANTIO_GATE_BLOCKED`)
- [x] Unix-socket / IPC path connects pass through
- [x] Out-of-scope hosts pass through (including plain `127.0.0.1` unless policy/Ollama names them)
- [x] Tests: raw net blocked never TCP; paid `http.get` still one ingest event
- [x] No new Mission Control copy

## Out of scope

curl · browsers · Python `socket` · WebSocket frames after upgrade · Stripe · stranger-host · TLS payload redaction
