# Spec — Spawn extras (SDK 3.0.9 · CLI 0.3.15)

**Brand:** Vantio Optics · Vantio Gate  
**Workflow:** Sight Loop · Rules that stick  
**Tier fence:** P0  
**Customer surface:** CLI (`vantio run`) · Python SDK · API (ingest)

Stripe live checkout, a second (stranger) host, and browsers stay parked. Chromium/CDP stays the named wrap gap. Do not add this leftover catalog to vantio.ai marketing copy.

## Goal

Close remaining **in-process** spawn holes agents actually use, on the same Optics observe / Gate host-block / size / spend path already sold. File contents are never ingested. Curl/wget bodies are still not rewritten. Phantom Engine remains the host-level close for paths this wrap never sees.

## Checklist

- [x] Stdin bodies (`curl -d @-` / `-T -` / `wget --post-file=-`): honest size from `fstat` when stdin is a regular file, or from Node `spawnSync` `input` length. Pipes stay 0. Contents are not read.
- [x] `curl -F` / `--form` multipart file size via `stat` (and `--form-string` literal length). Contents never ingested.
- [x] `wget -i` / `--input-file` URL lists: parse destination lines (cap 64KiB / 32 URLs). A blocked dest never starts the child.
- [x] Extra CLIs `httpie` (`http` / `https` / `httpie`) and `aria2c` (`aria2c` / `aria2`) only as argv URL host-block after existing prefix/curl detection. No body rewrite.
- [x] Python and Node parity.
- [x] Tests: blocked dest never starts; fetch/urllib still one event; file contents never ingested.
- [x] No new Mission Control copy. No vantio.ai leftover dump.

## Out of scope

browsers · Chromium/CDP · Stripe · stranger-host · rewriting curl/wget bodies for PII · TLS MITM · pycurl · grpc C-core · native addons · dgram / HTTP3
