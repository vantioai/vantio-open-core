# Spec — Wrap wget spawned from Node (CLI 0.3.12)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.6**.

## Goal

When a wrapped Node agent spawns `wget` (including `sh -c 'wget …'`) to an in-scope host, that spawn shares host-block and observe with fetch and curl. A blocked destination never starts wget. `--post-data` / `--body-data` byte length can trip a size cap. Wget payloads are not redacted.

Browsers stay residual. Python `subprocess` wget is a follow-on.

## Checklist

- [x] Existing curl spawn wrap still blocks / observes as `node_curl`
- [x] Wrap spawn/exec when the program is wget (`sh -c 'wget …'` included)
- [x] Blocked host: wget process never starts (`VANTIO_GATE_BLOCKED`)
- [x] Allowed / observe: ingest `node_wget` with `bytes_observed`
- [x] Regular fetch still one ingest event (not `node_wget`)
- [x] No new Mission Control copy

## Out of scope

browsers · Python subprocess wget · `--post-file` body size · Stripe · stranger-host · rewriting wget bodies for PII
