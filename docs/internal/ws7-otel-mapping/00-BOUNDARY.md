# WS7 I2 — OpenTelemetry semantic mapping boundary

PRIVATE | INERT | NOT SHIPPED | ADAPTERS DISABLED | NO OTLP EXPORTER | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Producer: cloud agent `bc-9df330d5-2a6d-5f71-bf38-2753d0b8261c`.

Producer URL: https://cursor.com/agents/bc-9df330d5-2a6d-5f71-bf38-2753d0b8261c

Producer classification on the failed tip `dd9359e7c374d21986b3c7ec57d69946328d2252`: `OTEL_MAPPING_DESIGN_READY_FOR_COUNCIL`

Revision classification: `OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL`

That classification means the revised design is ready for a separate council. It is not a council verdict, not an exporter, and not a public support claim. Council previously returned `OTEL_MAPPING_DESIGN_NEEDS_REVISION`. This revision does not merge, does not enable adapters, and does not authorize I3.

## Locked input

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Starting `origin/main` | `5064f32f1cdfcb840dfd100e2ce5c712d046550d` |
| Branch | `cursor/ws7-otel-mapping-design-261c` |
| Mapping | `WS7-I2` version `0` |
| Schema | `schema_status` `unstable-pre-1.0`, `stable_schema` false, `schema_url` null |
| Package | `@vantio/optics-otel-mapping` `0.0.0-unstable-pre-1.0`, private, not a pnpm workspace member |
| Public sketch | `docs/optics-otel-mapping.md`, left unchanged |
| Founder decision 12 | Unresolved. No OTLP exporter is authorized. |

## What this force does

- Pins a versioned correspondence between Optics fields and OpenTelemetry semantic conventions.
- Records which correspondences are candidates, which are refused, and which stay unresolved.
- Adds a private package whose three adapters default to disabled and whose export function stays disabled.
- Leaves `03-PENDING-COUNCIL.md` as `PENDING_COUNCIL`.

## What this force keeps closed

- Live CLI `0.3.24`, Python `3.1.0`, and Node SDK `0.2.4`.
- `@vantio/optics-evidence-contract` and `@vantio/optics-record-vocabulary`.
- The public sketch, product manual, website, and any announcement.
- An OTLP client, collector, listener, proxy, or daemon.
- An enable flag. I3 is later and is not authorized by this packet.
- A stable schema, a schema URL, a release, a tag, or a publish.
- Founder decisions 2 through 13. Decision 12 stays unresolved.

## Hard stops

| Stop | Attestation |
| --- | --- |
| No public shipped support | `public_shipped_support` is false. The public sketch still says Optics does not export OTLP. |
| Adapters default disabled | `otlp_traces`, `otlp_metrics`, and `otlp_logs` have `default_enabled` false and `implementation` `NOT_PRESENT`. |
| No enable path | `exportOpticsRecords` returns `ADAPTERS_DISABLED` when a caller passes `enabled: true`. |
| No network | Package source does not require `http`, `https`, `net`, or an OpenTelemetry SDK. |
| No content | `gen_ai.input.messages`, `gen_ai.output.messages`, and `gen_ai.system_instructions` are `DO_NOT_MAP`. |
| No token invention | Byte counts are not `gen_ai.usage.input_tokens` or `gen_ai.usage.output_tokens`. |
| I3 not started | `i3_status` is `NOT_AUTHORIZED`. |
| Council is separate | This producer did not write a council verdict. |
