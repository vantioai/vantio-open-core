# PKG-02 Unit B — no optimistic defaults

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

`SUCCESS` stays in the `optics_status` enum because PKG-01 lists it. This adapter does not store it. A missing token, an unknown token, and a legacy `opticsStatus` `SUCCESS` all read as `UNAVAILABLE`. Explicit `OBSERVED` is kept.

| Condition | Detached reading |
| --- | --- |
| `optics_status` missing | `UNAVAILABLE`. Not `SUCCESS`. Not `OBSERVED`. |
| Legacy `opticsStatus` `SUCCESS` | `UNAVAILABLE` and `optimistic_default_forbidden` |
| Unknown token such as `SUPER_SUCCESS` | `UNAVAILABLE` and `optimistic_default_forbidden`. The raw token is absent. |
| Explicit `OBSERVED` | Preserved |
| Explicit canonical `SUCCESS` | Refused as `UNAVAILABLE` on this inert adapter |
| `action` missing | Key omitted |
| HTTP status missing or null | Key omitted. Not `200`. Not `0`. |
| Bytes missing | `response_bytes` omitted |
| Legacy `bytes` `0` | `response_bytes` null |
| Explicit `response_bytes` `0` | `0` |
| Origin missing | Reader label `LEGACY_UNMARKED`. Not stored as `LOCAL_OBSERVATION` |
| Claimed local without producer and version | `LEGACY_UNMARKED` |
| Inherited trace | `ASSERTED_CONTEXT` |
| Empty `calls` array | `NOT_OBSERVED` on `optics_health` and on the detached envelope `optics_status` |
| Inherited trace envelope | `optics_status` `UNAVAILABLE` on the detached record, `trace_id_basis` `ASSERTED_CONTEXT` |
| Absent file | `UNAVAILABLE`. Not `NOT_OBSERVED` |
| Corrupt JSON or unreadable bytes | `OPTICS_ERROR`. Not an empty success record |
| Invalid `sampling` | Omitted. Not stored as `UNSAMPLED`. The same omission applies to a JSON string and to bytes |
| HTTP 200–399 | Workload `application_status` `SUCCESS`, including 302. Not copied into `optics_status` |
| HTTP 500 | `application_status` `APPLICATION_ERROR`, `issue_location` `PROVIDER_INTERACTION`, optics `UNAVAILABLE` |

Frozen `displayCall` still returns optics `SUCCESS` for a call row. That pairing is unsupported. This unit does not change `optics-cx.cjs`.
