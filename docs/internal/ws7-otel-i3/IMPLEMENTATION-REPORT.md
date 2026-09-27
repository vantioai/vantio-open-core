# WS7 I3 implementation report

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification: `OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED`

This report is not a council verdict and not a merge instruction. `council` remains `PENDING_COUNCIL`.

## What landed

Private package `@vantio/optics-otel-i3`. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, Python `3.1.0`, the evidence contract, the record vocabulary, or the WS7-I2 mapping package.

The mapping document is still version `0`, id `WS7-I2`, `i3_status` `NOT_AUTHORIZED`, `otlp_export_authorized` false. The new adapter fails closed if that identity changes.

Traces can be sent only by an explicit call. The module default is disabled. Metrics and logs have no implementation. The wire format is OTLP/HTTP JSON. Protobuf is not implemented.

`docs/optics-otel-mapping.md` is unchanged.

## Checks

From the repository root:

```sh
node --test tests/optics-otel-i3/*.test.cjs
node --test tests/optics-otel-mapping/*.test.cjs
node --test docs/scripts/check-docs-release.test.mjs
```

`node --test tests/optics-otel-i3/*.test.cjs` reported 38 tests and 0 failures. Those tests cover field and version mapping, unknown fields, disabled calls, backpressure, an unavailable exporter, retry bounds, drop evidence, a customer endpoint, and authority that stays equal when the exporter accepts or fails. They also cover credential, content, kernel, company-operation, and proof-field withholding, plus a local HTTP client that does not follow redirects.

`node --test tests/optics-otel-mapping/*.test.cjs` reported 25 tests and 0 failures. The mapping package is unchanged.

`node --test docs/scripts/check-docs-release.test.mjs` still reports `legacy-stale-name-inventory-frozen` for `tests/shared-health-vocabulary/collision.test.cjs`. That file is on starting main `89f95099` and is outside this diff.

## Hard-stop attestations

- No CLI, Python SDK, or Node SDK source change.
- No evidence-contract, record-vocabulary, or mapping-package change.
- No public sketch change and no shipped-support sentence.
- No stable schema and no schema URL.
- No release, seal, publish, tag, or announcement.
- Founder decision 12 stays unresolved.
- Council is a separate agent. This producer did not run it.
