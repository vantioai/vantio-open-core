# WS7 I2 — adapter stub boundaries

PRIVATE | INERT | NOT SHIPPED | ADAPTERS DISABLED | NO OTLP EXPORTER | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

I3 is later. This file bounds the stub. It does not implement an exporter.

## Adapters in mapping version 0

| Id | Signal | Default | Implementation | Network |
| --- | --- | --- | --- | --- |
| `otlp_traces` | traces | disabled | `NOT_PRESENT` | no |
| `otlp_metrics` | metrics | disabled | `NOT_PRESENT` | no |
| `otlp_logs` | logs | disabled | `NOT_PRESENT` | no |

`adapters_default_enabled` is false. `exportOpticsRecords` returns `exported: false`, `reason: ADAPTERS_DISABLED`, `network: false`, and `bytes_sent: 0`. A caller option `{ enabled: true }` does not change that result. The function counts records and does not copy their fields, so a prompt in the input is not echoed.

There is no `enableAdapter`, no OTLP client, and no console dump. A local dump would be another exporter. This stub does not add one.

`preview` returns candidates for review. `emitted` on that object is false. Candidates are not a payload a process can hand to a collector from this package.

## What a future adapter would still have to obey

These bounds apply before any enable flag exists:

- Default remains disabled. An unset flag is disabled.
- A present `evidence_origin` other than `LOCAL_OBSERVATION` stays out of the candidate set on both `live_display` and `canonical_observation`. That includes `SIMULATED_DEMO`, `TEST_FIXTURE`, `IMPORTED`, `PRODUCT_HEALTH`, `DERIVED_DIAGNOSTIC`, and any other non-local origin. Client span status stays null. `emitted` stays false. `would_be_operational_if_i3_enabled` stays false.
- A missing origin on `canonical_observation` stays out of the candidate set. A `live_display` row with no `evidence_origin` may keep non-operational field candidates.
- Live display rows stay non-operational until a writer stamps `LOCAL_OBSERVATION` on a canonical observation.
- Content attributes stay off. Byte counts stay off token attributes.
- Metric labels, if a metrics adapter is ever built, stay on low-cardinality enums. `provider_id` is not a metric label in the evidence catalog. `run_id`, `trace_id`, `session_id`, `path`, and raw `destination_host` are not metric labels.
- The package must not patch `fetch`, install an OpenTelemetry hook, or set `OTEL_SEMCONV_STABILITY_OPT_IN`.
- Founder decision 12 has to be resolved by a Founder before any network export. This packet does not resolve it.

## I3 template

```
NOT AUTHORIZED
DRAFT FOR FOUNDER REVIEW
DO NOT EXECUTE
```

FOUNDER FORCE — WS7 I3 OPENTELEMETRY ADAPTER (NOT AUTHORIZED)

Starting main must be a descendant of this I2 branch that a Founder names. On mismatch, stop.

Writable later, only after that authorization:

- `packages/optics-otel-mapping/` enable path, still defaulting to disabled
- tests that prove the flag off leaves `bytes_sent` at 0

Still closed unless a later force says otherwise:

- live CLI, Python SDK, Node SDK
- public docs that would claim shipped support
- a default-on exporter
- prompt or completion capture
- token counts derived from bytes

Success token for that later force is not chosen here. This revision stops at `OTEL_MAPPING_DESIGN_REVISION_READY_FOR_COUNCIL`. I3 stays `NOT_AUTHORIZED`.
