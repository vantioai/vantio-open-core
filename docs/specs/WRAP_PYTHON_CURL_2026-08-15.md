# Spec — Wrap Python subprocess curl (SDK 3.0.6)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run python`) · SDK · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Node CLI stays **0.3.11**.

## Goal

When a wrapped Python agent starts `curl` via `subprocess` (including `shell=True` / `sh -c 'curl …'`), `os.system`, or `asyncio.create_subprocess_*` to an in-scope host, that spawn shares host-block and observe with urllib. A blocked destination never starts curl. Request-body bytes from `-d` / `--data*` can trip a size cap. Curl payloads are not redacted.

Browsers stay residual.

## Checklist

- [x] Wrap `subprocess.Popen` (covers `run` / `call` / `check_*`) when the program is curl
- [x] `sh -c 'curl …'` and `shell=True` are treated as curl
- [x] `os.system` and `asyncio.create_subprocess_exec` / `create_subprocess_shell` for curl
- [x] Blocked host: curl process never starts (`GateBlockedError` / `VANTIO_GATE_BLOCKED`)
- [x] Allowed / observe: run log + ingest `python_curl` with `bytes_observed`
- [x] urllib still one run-log event (not `python_curl`)
- [x] No new Mission Control copy

## Out of scope

browsers · wget · `curl -K` config files without a URL on argv · Stripe · stranger-host · rewriting curl bodies for PII
