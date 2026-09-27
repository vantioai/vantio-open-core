# Harness

PRIVATE | DEFAULT DISABLED | NOT SHIPPED | NO PUBLIC OTLP EXPORT | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`runEnableTestDisable()` is the only enable path in this force. It takes no endpoint argument. The call uses `http://127.0.0.1:9/v1/traces` and an in-process transport. `dialed` on the report is false.

## Phases

| Phase | What the call does |
| --- | --- |
| Rest before | `adapterStatus()` and the mapping adapter list are disabled. `i3_status` is `NOT_AUTHORIZED`. |
| Disabled before | A traces call without boolean `enabled: true` returns `ADAPTER_DISABLED`, `bytes_sent` 0, and does not call the transport. |
| Enable and test | The harness passes `enabled: true` and `adapter: "otlp_traces"` for the attempts below. |
| Disable | String `"true"`, an inherited `enabled` flag, and a call that omits `enabled` each return `ADAPTER_DISABLED` with `bytes_sent` 0. |
| Rest after | The same disabled rest state as the start. `left_disabled` is true. `phase` is `DISABLED`. |

## Attempts

| Id | Result the proof records |
| --- | --- |
| `accepted` | In-process HTTP 200. `exported` true. `bytes_sent` equals the encoded body. `bytes_dropped` is 0. `public_shipped_support` is false. |
| `exporter_unavailable` | The transport throws. `bytes_sent` is 0. `bytes_dropped` equals the encoded body. Reason `EXPORTER_UNAVAILABLE`. |
| `nothing_to_export` | An empty record list. `bytes_sent` is 0. The transport is not called. |
| `product_health` | `PRODUCT_HEALTH` yields an empty candidate set, `bytes_sent` 0, and no transport call. |
| `optics_success` | `optics_status` `SUCCESS` leaves span status unset (code 0). |
| `success_without_http` | `application_status` `SUCCESS` without an HTTP status leaves span status unset and omits `http.response.status_code`. |
| `prompt_completion` | Prompt and completion text stay out of the result. Token attributes stay absent. `bytes_sent` is 0. |
| `live_identity` | A live `provider` and a live 32-hex `trace_id` stay out of OTEL identity. `bytes_sent` is 0. |
| `mapping_package_stays_disabled` | The mapping package still returns `ADAPTERS_DISABLED` when the harness passes `enabled: true`. |
| `otlp_metrics`, `otlp_logs` | `SIGNAL_NOT_AUTHORIZED`, `enabled` false, `bytes_sent` 0. |

Authority for an eligible record is still computed when metrics or logs are selected. That computation is not a send. `transport_calls` stays 0 and `encoded_bytes` stays 0.

An accepted harness attempt is an internal byte count. It does not change `public_shipped_support`, `product_otlp_export_authorized`, or `i3_status`.
