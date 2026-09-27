# PKG-02 Unit E record delta

Audience: INTERNAL_RESTRICTED

Against a sealed `3.1.0` file from the same class of workload, a canonical file from this line shows:

| Item | Future file | Sealed `3.1.0` file |
| --- | --- | --- |
| `runtime` | `python` | `python` |
| `producer` | `python_observe` | absent |
| `schema_version` | `0` | `2` |
| Legacy `2` | `compatibility.legacy_schema_version` | the stored schema version |
| Timestamps | UTC `Z` with three fractional digits | `+00:00` with microseconds |
| `duration_ms` | present only when the interval was measured | present on completed calls |
| `failure_kind` | kept when the call had one | kept on transport failures |
| `provider` / `provider_id` | omitted | `provider` `other` on the call |
| Envelope `mediation` | omitted; each event keeps one enum token | comma-joined string |
| `response_bytes` | omitted when the size is missing; explicit `0` stays `0` | size often omitted; `bytes_observed` on some paths |
| `optics_status` | `OBSERVED` when the call was seen, including an unavailable provider outcome | `opticsStatus` `SUCCESS` |
| `application_status` | HTTP map on the event | call token, with run rollup `PARTIAL` when mixed |
| Mixed outcomes | envelope `lifecycle` `PARTIAL` | summary `applicationStatus` `PARTIAL` |
| Empty `shield()` | explicit `NOT_OBSERVED` bundle | no file |
| Unicode diagnostic | `PKG01-UCD-16.0.0` | absent |
| `workflow`, `status_labels`, `plane`, `data_note`, `residual` | absent | present |

Shared fixture `packages/vantio-agent-sdk-py-future/fixtures/shared-semantic-observation.json` is an HTTP 404 observation. Its sealed event, the Python canonical JSON, and the Node adapter canonical JSON are the same bytes.
