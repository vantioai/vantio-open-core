# Spec — Wrap completeness batch (SDK 3.0.8 · CLI 0.3.14)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · Python SDK · API (ingest) · vantio.ai supported list · Mission Control (events only — no extra chrome)

Stripe live checkout, a second (stranger) host, and browsers stay parked. Chromium/CDP stays the forever-named residual.

## Goal

Close the remaining **in-process** wrap leftovers in two version bumps, not one library per continue. File-body size, skipped stdlib/http stacks, spawn prefixes, curl config URLs, and WebSocket handshake host-block share the same Optics observe / Gate host-block / size / spend path already sold. Curl/wget bodies are still not rewritten. Phantom Engine remains the host-level close for paths this wrap never sees.

## Wave 1 — `vantio-agent-sdk` 3.0.8

- [x] File-body size via `os.stat` for `curl -d @file` / `--data*` / `-T` and `wget --post-file` / `--body-file` (stdin `-` stays 0; contents never read)
- [x] `socket.connect_ex` shares host-block / observe with `connect`
- [x] `http.client` `request` / `putrequest` — host / size / spend; PII when body is `bytes`/`str`
- [x] urllib3 when installed (`HTTPConnectionPool.urlopen`, so GateBlockedError is not swallowed by retries)
- [x] httpx redaction write-back onto the request
- [x] `urllib.request.OpenerDirector.open` (custom openers, not only `urlopen`)
- [x] `curl -K` / `--config` URL lines on Python spawn parse
- [x] Spawn prefixes `env` / `timeout` / `nice` for curl/wget
- [x] urllib still one run-log event (not `python_socket` / `python_wget`)
- [x] No new Mission Control copy

## Wave 2 — `@vantio/cli` 0.3.14

- [x] `curl -K` / `--config`: if argv has no URL, read `url =` / `url=` lines only
- [x] Spawn prefixes `env` / `timeout` / `nice` so `timeout 5 curl …` is still curl/wget
- [x] `http.ClientRequest` constructor hits the existing http wrap
- [x] `globalThis.WebSocket` / `undici.WebSocket` host-block; outbound frame size only (no payload redaction)
- [x] Fetch still one ingest event
- [x] No new Mission Control copy

## Out of scope

browsers · Chromium/CDP · Stripe · stranger-host · stdin `@-` · rewriting curl/wget bodies for PII · TLS MITM · pycurl · grpc C-core · native addons · dgram / HTTP3 · httpie / aria2c · `wget -i` · `curl -F` multipart file size
