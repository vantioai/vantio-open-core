# WS7 I3 boundary

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification: `OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED`

That token means this adapter is ready for a separate council. It is not a council verdict, not a public support claim, and not a resolution of Founder decision 12.

## What this force builds

- Private package `@vantio/optics-otel-i3` at `0.0.0-unstable-pre-1.0`.
- A default-disabled OTLP/HTTP JSON traces path that consumes the approved mapping preview.
- Tests for field and version mapping, unknown fields, disabled behavior, backpressure, an unavailable exporter, retry bounds, drop evidence, a customer-controlled endpoint, and authority that does not depend on the exporter.

The package is not in `pnpm-workspace.yaml`. It has no dependencies. It loads `@vantio/optics-otel-mapping` by a relative path.

## What stays closed

- `packages/optics-otel-mapping/`, including `i3_status` `NOT_AUTHORIZED` and `implementation` `NOT_PRESENT`.
- Live CLI `0.3.24`, Python `3.1.0`, and Node SDK `0.2.4`.
- `@vantio/optics-evidence-contract` and `@vantio/optics-record-vocabulary`.
- `docs/optics-otel-mapping.md` and the other public product docs.
- A stable schema, a schema URL, a release, a tag, a seal, or a publish.
- Metrics and logs. Mapping version 0 has no rows for those signals.
- Protobuf OTLP and an OpenTelemetry SDK.
- Environment-variable enablement, including `OTEL_EXPORTER_OTLP_ENDPOINT`.
- Credential headers, endpoint userinfo, and query secrets.
- Prompts, completions, customer content, kernel details, unrelated company operations, and proof claims.

## Hard stops

| Stop | Attestation |
| --- | --- |
| Default disabled | `enabled` must be the boolean `true` and `adapter` must be `otlp_traces`. Any other call returns `bytes_sent` 0 and does not call a transport. |
| No public export claim | `public_shipped_support` is false. `product_otlp_export_authorized` is false. The public sketch is unchanged. |
| Mapping identity | The adapter refuses to load if the mapping document is not WS7-I2 version 0 with `i3_status` `NOT_AUTHORIZED`. |
| No content | Prohibited names and credential-shaped values are withheld. They are not copied into the result or the JSON body. |
| No invented identity or clock | Missing W3C context is not filled in. `duration_ms` is not a span time. Equal or missing unix-nano bounds are not sent. |
| No authority flip | Exporter success, HTTP 429, connection failure, and a disabled call share the same authority object for the same records. |
| Council is separate | This producer did not write a council verdict. `council` is `PENDING_COUNCIL`. |
