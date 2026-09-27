# Optics PKG-02 — Node and Python delta

Audience: INTERNAL_RESTRICTED

Node in this delta means the CLI interceptor run log, which is the live Node-shaped writer. `@vantio/agent-sdk` `0.2.4` is called out where it differs. It does not write that log.

Each row is a mismatch a future adapter must keep visible. Classes are defined in `RECORD-VOCABULARY.json`.

## 1. Optimistic defaults that are now locked

| Condition | Required disposition | Live behavior this forbids as a future default |
| --- | --- | --- |
| `optics_status` absent | `UNAVAILABLE`, reason `MISSING_REQUIRED_STATUS` | CLI display and Python `_record` use `SUCCESS` |
| `action` absent | Omit. Do not store `OBSERVED` | Both writers always set an action, including enforcement tokens |
| HTTP status absent | Omit `http_status`. Do not store `200` or `0` | Neither writer invents `200`. CLI dispatch stores `status: null` and `ok: true` |
| Byte count absent | Omit `response_bytes`. Legacy `bytes` `0` becomes null. Explicit `response_bytes` `0` stays `0` | CLI exit map stores `call.bytes \|\| 0` |
| Origin absent | Reader label `LEGACY_UNMARKED` | Neither writer stores origin, so a naive reader could assume local observation |
| Inherited trace | `ASSERTED_CONTEXT`, not `OPTICS_GENERATED` | CLI copies `VANTIO_TRACE_ID` into `trace_id` with no basis |
| Unknown enum | Not success. Unknown optics token becomes `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN` | Live display has no path that preserves an unknown token |
| Corrupt input | Reject. Not an empty valid record | MCP skips corrupt files. CLI `failUnreadable` reports them on some commands |
| Reader cannot read | `UNAVAILABLE` or `OPTICS_ERROR`. Not `NOT_OBSERVED` | `status` uses `NOT_OBSERVED` for a missing run directory, which is closer, and `OPTICS_ERROR` for unreadable bytes |
| Failure detail absent | Not a success proof | Python still stores `opticsStatus` `SUCCESS` when the provider outcome is unavailable |

`null`, absent, `unknown`, `UNAVAILABLE`, `UNSUPPORTED`, invalid, prohibited, and `LEGACY_UNMARKED` stay different:

| Token or state | Meaning |
| --- | --- |
| Absent | The writer did not have the field. Readers do not invent one. |
| `null` | The writer had the field and the value is empty by rule, such as envelope `span_id` or a rejected trace stored as null. |
| `unknown` | A closed-enum fallback for scheme, method, mediation, or provider id. It is not success. |
| `UNAVAILABLE` | The dimension was considered and the evidence was not available. |
| `UNSUPPORTED` | The client or path is outside the supported set. CLI `sdkRows` uses this word for "package not importable," which is a different dimension and must not be copied into `optics_status`. |
| Invalid | `REJECT_FIELD` or `REJECT_RECORD`. The value is not stored. |
| Prohibited | Strip or reject. The name and the secret value are not stored. |
| `LEGACY_UNMARKED` | Reader label. Origin was missing or provenance was insufficient. |

## 2. Special review

### Timestamps

CLI stores `Z` milliseconds. Python stores `+00:00` microseconds. The contract normalizes both to `Z` with three digits and rejects non-zero offsets. `generated_at` is write time, mapped to `ended_at` only by the adapter. Class: `SEMANTIC_MISMATCH` for `ended_at` on both. `started_at` is `EXACT_MATCH` on CLI and `SEMANTIC_MISMATCH` on Python because of the stored form.

### Duration units

Both use integer milliseconds. Python socket intervals use `perf_counter`. Python HTTP and CLI fetch use wall clocks. `clock_quality` is missing on both, so the unit match is not a clock match. CLI dispatch stores `duration_ms` `0` before the call finishes. That row is `SEMANTIC_MISMATCH` on CLI and `EXACT_MATCH` on Python for a completed interval.

### Process ids

CLI stores numeric `pid` and `ppid`. Python stores neither. Node SDK may send `pid` only inside an ingest payload. No writer stores a string pid. There is no `TYPE_MISMATCH` on the catalog process fields.

### HTTP redirects

Neither writer records intermediate hops. A 3xx final status becomes `application_status` `SUCCESS` under the shared 200–399 rule. That success is the workload token for a redirect response. It is not `optics_status` `SUCCESS`, and it is not evidence the redirect target was observed as its own event.

### Async

CLI `wrapFetch` records after the promise settles. `applyDispatchGate` records before the response. Python asyncio hooks record after the response or the exception. A pre-completion row must not be stored as `lifecycle` `COMPLETE`.

### Exception classification

Python stores `failure_kind` and `error_class`, and it lets a final HTTP status win over a nested transport error. CLI stores `error_class` and `error` `network_error` on the fetch catch, with no `failure_kind`. A customer exception Python marks `wrapped` becomes issue location `CUSTOMER_APPLICATION` when no HTTP status exists. CLI does not make that split. The string `network_error` is not the enum.

### Bytes versus zero

CLI persists `0` for a missing response size and adds those zeros into `summary.total_bytes`. Python omits response size and still stores `opticsStatus` `SUCCESS`. Explicit contract `response_bytes` `0` remains a real zero. Legacy `bytes` `0` becomes null. `request_bytes` on CLI may be null. Python HTTP omits `request_bytes`. Python subprocess uses `bytes_observed`.

### Provider identity

Both store a `provider` string. The contract strips it and sets `provider_id` `unknown` with confidence `NONE` unless the caller supplied an allowlisted `provider_id`. Guessing from the hostname is not that token.

### Empty and no-call runs

CLI writes an envelope with `calls: []`. Display rollup of that file is `NOT_OBSERVED` / `NOT_OBSERVED`. Python writes no file. `empty_observation()` is not a file. A missing Python file is not the same evidence as a CLI empty file. Future readers say which of those two happened. They do not treat a missing file as `SUCCESS`.

### Local observation versus inherited context

Neither writer stores `evidence_origin`. CLI and Python `shield()` will both persist whatever trace string they were given. That string is inherited context when it came from the environment or the caller. It becomes `run_id` in the adapter. It does not become `trace_id_basis` `OPTICS_GENERATED`.

### Streaming

CLI paid fetch starts `bytes` at `0` and may update the same object when a content-length-less body is counted later. If the process exits first, the file keeps `0`. Python does not store that response size at all. A future writer omits `response_bytes` until the count is finished, and it sets `lifecycle` `PARTIAL` or `INTERRUPTED` when the stream did not finish.

### Partial and interrupted

Live `PARTIAL` is a mixed application rollup. It is not `lifecycle` and not `optics_status`, except that the optics enum also contains the token and the live optics rollup does not use it for that mix. Future records use `lifecycle` for the attempt and keep per-call application tokens. They do not store one `application_status` of `PARTIAL`.

### Customer exceptions

Python `wrapped` plus `error_class` is the customer-exception path. CLI stores `error_class` on network failures and does not store `failure_kind`. An absent `failure_kind` must not be read as `none`, and `none` must not be read as workload `SUCCESS`.

### Unsupported clients

Out-of-scope hosts are not recorded. Browsers are outside the wrap. That silence is a coverage limit. It is not `UNSUPPORTED` stored as success, and it is not `NOT_OBSERVED` unless the wrap ran and the in-scope call list is empty. `sdkRows` `UNSUPPORTED` means a provider package did not resolve. That token must not be written into an observation.

### Schema markers

Both files use `schema_version` `2` and `vantio_run_log` `"1"`. Python also stores `schema_status` `unstable-pre-1.0`. The CLI run file does not. CLI stdout does, via `withSchema`. The contract record always stores `schema_status` `unstable-pre-1.0` and `schema_version` `0`. The legacy integer survives only on `compatibility.legacy_schema_version`.

Python shape detection is `runtime == "python"` or `workflow == "sight_loop"`. `workflow` is a prohibited field and a shape detector at the same time. Future Python records use `runtime` `python` and `producer` `python_observe`. They do not need `workflow` to be recognized.

## 3. Node SDK delta

`reportAnomaly` is cloud ingest, not a run log. `timestamp_ns` is a `TYPE_MISMATCH` against RFC3339. `traceId` is camelCase and is not contract `trace_id`. `action_taken` overlaps the enforcement vocabulary the contract excludes. No future PKG-02 unit turns this SDK into the local writer. That choice is `NOT_YET_DECIDED` in the matrix.

## 4. What is not a mismatch

`scheme`, `path`, and `error_class` use the same names and the same broad types on both live call rows. `error_class` still has to pass the contract token grammar. A name the grammar rejects is invalid, not a second language dialect.

`applicationStatusFromHttp` in the contract matches `optics-cx.cjs` for integer statuses. Python `_application_status` uses the same split. The mismatch is the key name, the missing CLI field, and the run-level `PARTIAL` token, not the integer map.
