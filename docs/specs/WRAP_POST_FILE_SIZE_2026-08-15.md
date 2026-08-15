# Spec — Curl/wget file-body size on spawn (CLI 0.3.13)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · API (ingest) · Mission Control (events only — no extra chrome)

Stripe live checkout and a second (stranger) host stay parked. Python SDK stays **3.0.7**.

## Goal

When a wrapped Node agent spawns `curl` or `wget` with a file body (`-d @file`, `--data @file`, `--post-file`, `--body-file`, `-T` / `--upload-file`), Gate can apply the same size cap as inline `-d` / `--post-data` using the file's byte length. The wrap does not read file contents and does not redact them. A blocked oversized body never starts the child.

Browsers stay residual. Stdin bodies (`@-`, `--post-file=-`) stay unnamed. Python subprocess file bodies are a follow-on.

## Checklist

- [x] `curl -d @file` / `--data @file` (and `--data-binary` / `--json`) count file size
- [x] `wget --post-file` / `--body-file` count file size
- [x] Oversized file body: child never starts (`VANTIO_GATE_BLOCKED` / `BLOCKED_SIZE`)
- [x] Inline `-d` / `--post-data` still works
- [x] File contents are not ingested or rewritten
- [x] No new Mission Control copy

## Out of scope

browsers · stdin `@-` · Python subprocess `--post-file` · Stripe · stranger-host · rewriting curl/wget bodies for PII
