# WS7 I3 inventory

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Starting main: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

Producer: cloud agent `bc-68190fc3-9914-54b7-8281-98513b14c308`

Producer URL: https://cursor.com/agents/bc-68190fc3-9914-54b7-8281-98513b14c308

This inventory is what that main already contained. It is not a claim that a public export path existed.

## Approved mapping

| Item | Value on this main |
| --- | --- |
| Package | `@vantio/optics-otel-mapping` `0.0.0-unstable-pre-1.0`, private, not a pnpm workspace member |
| Document | `packages/optics-otel-mapping/mapping/otel-semantic-mapping.json` |
| `mapping_id` | `WS7-I2` |
| `mapping_version` | `0` |
| `schema_status` | `unstable-pre-1.0` |
| `schema_url` | null |
| `producer_classification` | `OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL` |
| `i3_status` | `NOT_AUTHORIZED` |
| `otlp_export_authorized` | false |
| `adapters_default_enabled` | false |
| `founder_decision_12` | unresolved |
| Adapter rows | `otlp_traces`, `otlp_metrics`, `otlp_logs`, each `implementation` `NOT_PRESENT` and `network` false |
| Export function | `exportOpticsRecords` returns `ADAPTERS_DISABLED`, `bytes_sent` 0, and does not copy record fields |
| Preview | `preview` fills candidates and sets `emitted` false. `would_be_operational_if_i3_enabled` is the design gate |

Allowlisted map targets in that document are `gen_ai.provider.name`, `gen_ai.operation.name`, `http.request.method`, `http.response.status_code`, `url.path`, `url.scheme`, `server.address`, `server.port`, and `error.type`.

Content attributes, token counts, model names, `gen_ai.system`, conversation id, `url.full`, machine hostname, and command lines are `DO_NOT_MAP`.

Operational candidates require `canonical_observation` with `evidence_origin` `LOCAL_OBSERVATION`. `live_display` stays non-operational. A present origin other than `LOCAL_OBSERVATION` yields an empty candidate set. Trace context is a candidate only for `APPLICATION_SUPPLIED` W3C ids. The mapping package does not emit a traceparent.

## Public product

`docs/optics-otel-mapping.md` says Optics does not export OTLP. Canonical known limitations say there is no OTLP exporter. CLI `0.3.24`, Node SDK `0.2.4`, and Python `3.1.0` do not load the mapping package.

Founder decision 12 is unresolved. This inventory does not resolve it.
