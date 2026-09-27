# Implementation report

Audience: INTERNAL_RESTRICTED

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Producer classification: `W3_OTLP_ENABLE_TEST_DISABLE_READY_FOR_COUNCIL`

## Added

- `internal/w3-otlp-enable-test-disable/` — private harness. `runEnableTestDisable` enables traces for one in-process proof and returns the adapter to the disabled rest state.
- `tests/w3-otlp-enable-test-disable/` — direct, honesty, and isolation tests.
- `docs/internal/wave3/otlp-enable-test-disable/` — boundary, harness, WS7 honesty, this report, the council slot, and `REST-REGISTER.json`.
- `docs/programs/production-readiness/wave3/OTLP-ENABLE-TEST-DISABLE.md` and `OTLP-REST-REGISTER.json`. The register copy is the same bytes as the internal register.

## What the cycle records

- Rest before and rest after: `default_enabled` false, mapping adapters disabled, `i3_status` `NOT_AUTHORIZED`.
- An accepted in-process attempt whose `bytes_sent` equals the encoded body, with `public_shipped_support` false.
- An unavailable exporter: `bytes_sent` 0 and `bytes_dropped` equal to the encoded body.
- Empty input, `PRODUCT_HEALTH`, prompts, completions, and live identity: `bytes_sent` 0 and no transport call.
- `optics_status` `SUCCESS` and application `SUCCESS` without an HTTP status: span status code 0.
- Mapping export stays `ADAPTERS_DISABLED`. Metrics and logs stay `SIGNAL_NOT_AUTHORIZED`.
- After the attempts, omitted `enabled`, string `"true"`, and an inherited `enabled` flag each return `ADAPTER_DISABLED` with `bytes_sent` 0.

## Left unchanged

- `@vantio/cli` `0.3.24`, `@vantio/agent-sdk` `0.2.4`, and Python `vantio-agent-sdk` `3.1.0`
- `pnpm-workspace.yaml`
- `@vantio/optics-otel-i3` and `@vantio/optics-otel-mapping`, including `default_enabled` false, `i3_status` `NOT_AUTHORIZED`, and `founder_decision_12` `unresolved`
- `docs/optics-otel-mapping.md`. That sketch still says Optics does not export OTLP.

## Verification

`node --test tests/w3-otlp-enable-test-disable/*.test.cjs`

That command reported 8 tests and 0 failures. The tests call `runEnableTestDisable` twice, check byte counts for the accepted and unavailable attempts, check the WS7 refusals, and check that both rest registers stay disabled.

## Hard-stop attestations

- The tip leaves `default_enabled` false and `enabled_at_rest` false.
- `public_shipped_support` stays false. `public_otlp_claim` stays false.
- Founder decision 12 stays `unresolved`. I3 product authorization stays `NOT_AUTHORIZED`.
- No CLI, Python SDK, or Node SDK source change.
- No publish, announcement, host attach, or customer deploy.
- Council is a separate agent. `council_verdict` is null.
