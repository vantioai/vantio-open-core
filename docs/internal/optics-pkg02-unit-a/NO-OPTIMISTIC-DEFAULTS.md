# PKG-02 Unit A — no optimistic defaults

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`SUCCESS` stays in the `optics_status` enum because PKG-01 lists it. Unit A does not use it as a stored reading. Every fixture prohibits `optics_status` `SUCCESS`. A fixture edited to store that token fails evaluation.

| Condition | Canonical reading | Fixture |
| --- | --- | --- |
| `optics_status` missing | `UNAVAILABLE`, not `SUCCESS`, not `OBSERVED` | `missing-status`, `successful-http-response` |
| Live `opticsStatus` `SUCCESS` | Refused. `UNAVAILABLE` and `OPTIMISTIC_DEFAULT_FORBIDDEN` | `python-3-1-0` |
| Unknown optics token | `UNAVAILABLE` and `OPTIMISTIC_DEFAULT_FORBIDDEN`. Raw token stays in the diagnostic | `unknown-status` |
| Explicit `OBSERVED` on a declared future input | Preserved. Not the missing-status default | `explicit-observed-not-default` |
| `action` missing | Key omitted | `missing-action` |
| HTTP status missing | Key omitted, not `200`, not `0` | `missing-status` |
| HTTP status null | Key omitted | `interrupted-run` |
| Bytes missing | `response_bytes` omitted | `bytes-missing` |
| Legacy `bytes` `0` | `response_bytes` null | `legacy-bytes-zero` |
| Explicit `response_bytes` `0` | `0` | `explicit-response-bytes-zero` |
| Origin missing | Reader label `LEGACY_UNMARKED`. Not stored as `LOCAL_OBSERVATION` | `cli-0-3-24` |
| Claimed local without producer and version | `LEGACY_UNMARKED` | `claimed-local-without-provenance` |
| Inherited trace | `ASSERTED_CONTEXT`, not `OPTICS_GENERATED` | `inherited-trace` |
| Unknown enum | Omitted from the canonical object. Raw token kept in the diagnostic | `unknown-enum` |
| Unreadable record | `OPTICS_ERROR`, not `NOT_OBSERVED` | `unreadable-record` |
| Absent file | `UNAVAILABLE`, not `NOT_OBSERVED` | `no-file`, `empty-shield` |
| Corrupt JSON | No record. Not `{}` | `corrupt-record` |
| Pre-completion `duration_ms` `0` | Omitted. Not a measured zero | `interrupted-run` |
| `sampling` other than `UNSAMPLED` | `UNSAMPLED`. Not optics success | `sampling-not-success` |
| `ok` | Not stored | `cli-0-3-24` |
| `failure_kind` `none` | Not copied as workload proof | `python-3-1-0` |

`NOT_OBSERVED` appears only on `cli-empty-call-file`, where the CLI file exists and `calls` is empty. That is the wrap-ran, nothing-stored case. It is not the reading for a missing path, a corrupt file, or an unreadable file.

HTTP 200–399 may set workload `application_status` `SUCCESS`, including 302. That token is not copied into `optics_status`. HTTP 400–599 sets `APPLICATION_ERROR`. The checker rejects a fixture that disagrees with that split.
