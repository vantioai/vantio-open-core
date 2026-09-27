# WS7 I3 adapter

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

Public functions on `@vantio/optics-otel-i3`:

| Function | Behavior |
| --- | --- |
| `adapterStatus()` | Returns the posture. `active` is false. `default_enabled` is false. |
| `evaluateRecords(records)` | Pure authority and eligibility. No socket. |
| `exportOpticsRecords(records, options)` | Same evaluation, then a send only when the call is explicitly enabled. |
| `parseCustomerEndpoint(value)` | Accepts or rejects a customer URL. Does not connect. |

`POSTURE.producer_classification` is `OTEL_I3_ADAPTER_READY_FOR_COUNCIL_DEFAULT_DISABLED`.

## Disabled

These calls do not select traces:

- omitted options
- `enabled` other than boolean `true`, including the string `"true"`
- `enabled: true` without `adapter: "otlp_traces"`
- `adapter` `otlp_metrics` or `otlp_logs`

The result has `enabled` false, `exported` false, `network` false, and `bytes_sent` 0. The endpoint string is not copied. An injected transport is not called.

`otlp_metrics` and `otlp_logs` return `SIGNAL_NOT_AUTHORIZED`. A missing or unknown adapter returns `ADAPTER_NOT_SELECTED` when `enabled` is true, and `ADAPTER_DISABLED` otherwise.

## Enabled traces

`enabled: true` and `adapter: "otlp_traces"` still send nothing until the endpoint parses and at least one record is queued.

| Condition | Reason | Transport |
| --- | --- | --- |
| Credential option present | `CREDENTIAL_OPTION_REJECTED` | not called |
| Endpoint missing or not a trace URL | `ENDPOINT_*` | not called |
| `transport` set and not a function | `TRANSPORT_INVALID` | not called |
| No queued span | `NOTHING_TO_EXPORT` | not called |
| Encoder or payload check fails | `ENCODE_REJECTED` | not called |
| HTTP 200 or 202 | `ACCEPTED` | called |
| HTTP 429 until the attempt cap | `BACKPRESSURE_EXPORTER` | called |
| Network failure or HTTP 5xx until the cap | `EXPORTER_UNAVAILABLE` | called |
| Other HTTP status | `EXPORTER_REJECTED` | called, no retry |

Drop evidence is an index, a phase (`eligibility`, `admission`, or `delivery`), a reason code, the mapping version, and an operational flag. It does not include record values.

## Clocks and identity

`start_time_unix_nano` and `end_time_unix_nano` are export bounds supplied on the record. They are not attributes. `duration_ms`, `clock_quality`, `run_id`, `session_id`, `process_id`, byte counts, and the stored `ok` boolean are not attributes and are not span times.

Trace ids come only from mapping preview trace context. Live `trace_id` values are not promoted, including when they are 32 hex digits.
