# PKG-02 Unit F — no optimistic defaults

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

`SUCCESS` stays in the `optics_status` enum because PKG-01 lists it. This reader does not display it as the optics token. A missing token, a null token, an unknown token, a corrupt file, and a legacy `opticsStatus` `SUCCESS` all read as `UNAVAILABLE` or, for corrupt input, `OPTICS_ERROR`. Explicit `OBSERVED` is kept.

| Condition | Reader display |
| --- | --- |
| `optics_status` missing | `UNAVAILABLE`. Input class `absent`. Not `SUCCESS`. Not `OBSERVED`. |
| `optics_status` null | `UNAVAILABLE`. Input class `null`. Not the same class as absent or unknown. |
| Unknown token such as `SUPER_SUCCESS` | `UNAVAILABLE` and `optimistic_default_forbidden`. Input class `unknown`. The raw token is absent. |
| Legacy or explicit `opticsStatus` `SUCCESS` | `UNAVAILABLE` and `optimistic_default_forbidden`. Input class `refused_success`. |
| Explicit `OBSERVED` | Preserved. Input class `enum`. |
| `action` missing | Key omitted |
| HTTP status missing or null | Key omitted. Not `200`. Not `0`. |
| Bytes missing | `response_bytes` omitted. Display token `absent`. |
| Legacy `bytes` `0` | `response_bytes` null. Display token `null`. |
| Explicit `response_bytes` `0` | `0`. Display token `0`. |
| Origin missing | Reader label `LEGACY_UNMARKED`. Not stored as `LOCAL_OBSERVATION`. |
| Claimed local without producer and version | `LEGACY_UNMARKED` |
| Empty `calls` array | `NOT_OBSERVED` |
| Absent file | `UNAVAILABLE`. Not `NOT_OBSERVED`. The path is not created. |
| Corrupt JSON or unreadable bytes | `OPTICS_ERROR`. Not an empty success record. |
| HTTP 200–399 | Workload `application_status` `SUCCESS`, including 302. Not copied into `optics_status`. |
| HTTP 500 | `application_status` `APPLICATION_ERROR`, `issue_location` `PROVIDER_INTERACTION`, optics `UNAVAILABLE` |

Frozen `displayCall` still returns optics `SUCCESS` for a call row. That pairing is unsupported. This unit does not change `optics-cx.cjs`. The reader explanation keeps the machine token beside any gloss, so workload `Successful` cannot be the only place a customer sees which dimension fired.
