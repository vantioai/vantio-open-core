# Spec — Wrap Python subprocess wget (SDK 3.0.7)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run python`) · SDK · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Node CLI stays **0.3.12**.

## Goal

When a wrapped Python agent starts `wget` via `subprocess` (including `shell=True` / `sh -c 'wget …'`), `os.system`, or `asyncio.create_subprocess_*` to an in-scope host, that spawn shares host-block and observe with urllib and curl. A blocked destination never starts wget. `--post-data` / `--body-data` byte length can trip a size cap. Wget payloads are not redacted.

Browsers stay residual.

## Checklist

- [x] Existing curl spawn wrap still blocks / observes as `python_curl`
- [x] Wrap `subprocess.Popen` / `os.system` / `asyncio.create_subprocess_*` when the program is wget
- [x] `sh -c 'wget …'` is treated as wget
- [x] Blocked host: wget process never starts (`GateBlockedError` / `VANTIO_GATE_BLOCKED`)
- [x] Allowed / observe: run log + ingest `python_wget` with `bytes_observed`
- [x] urllib still one run-log event (not `python_wget`)
- [x] No new Mission Control copy

## Out of scope

browsers · `--post-file` body size · Stripe · stranger-host · rewriting wget bodies for PII
