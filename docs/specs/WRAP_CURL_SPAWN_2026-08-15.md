# Spec — Wrap curl spawned from Node (CLI 0.3.11)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.5**.

## Goal

When a wrapped Node agent spawns `curl` (including `sh -c 'curl …'`) to an in-scope host, that spawn shares host-block and observe with fetch. A blocked destination never starts curl. Request-body bytes from `-d` / `--data*` can trip a size cap. Curl payloads are not redacted.

Browsers stay residual. Python `subprocess` curl is a follow-on.

## Checklist

- [x] Wrap `child_process.spawn` / `spawnSync` / `execFile` / `exec` (and Sync) when the program is curl
- [x] `sh -c 'curl …'` is treated as curl
- [x] Blocked host: curl process never starts (`VANTIO_GATE_BLOCKED`)
- [x] Allowed / observe: ingest `node_curl` with `bytes_observed`
- [x] Regular fetch still one ingest event (not `node_curl`)
- [x] No new Mission Control copy

## Out of scope

browsers · Python subprocess curl · Stripe · stranger-host · rewriting curl bodies for PII
