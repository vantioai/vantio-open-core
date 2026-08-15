# Spec — Inline spawn body redaction (SDK 3.0.10 · CLI 0.3.16)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · Python SDK · API (ingest)

Stripe live checkout, a second (stranger) host, and browsers stay parked. Chromium/CDP stays the named wrap gap. Do not add a leftover catalog to vantio.ai marketing copy. Public wrap sentences already cover spawned curl/wget; omitting httpie/aria2c/`wget -i`/`curl -F` size is under-claim, not a lie.

## Goal

When Gate `redact_pii` is on, rewrite **inline argv bodies** for spawned curl/wget (and httpie when the body is on argv) so PII is stripped before the child starts. File contents and stdin pipes are not read. Phantom Engine remains the host-level close for paths this wrap never sees.

## Checklist

- [x] `curl` inline `-d` / `--data*` / `--data-raw` / `--json` (and inline `-F` / `--form-string` when the value is not `@file` / `<file`): redact argv text; `@file` / `-T` / stdin stay unreadable
- [x] `wget --post-data` / `--body-data` literals: same. `--post-file` / `--body-file` skipped
- [x] `httpie` (`http` / `https` / `httpie`) `--raw` and `name=value` / `name:=value` request items when the value is not a file. aria2c stays URL host-block only
- [x] Blocked dest still never starts. Fetch/urllib still one event. File contents never ingested
- [x] pycurl: wrap `pycurl.Curl()` via a Python proxy (C type methods are immutable). Host-block / size / spend / POSTFIELDS PII. Skip `READDATA` / `HTTPPOST` file bytes
- [x] Python and Node parity for argv rewrite
- [x] No new Mission Control copy. No vantio.ai residual dump

## Out of scope

browsers · Chromium/CDP · Stripe · stranger-host · TLS MITM / TLS payload redaction · reading file bodies or stdin pipes to redact · grpc C-core · native addons · dgram / HTTP3 · `from pycurl import Curl` before wrap install (named miss; C type has no class-method hook)
