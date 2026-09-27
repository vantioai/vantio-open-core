# PKG-02 Unit C design

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

## Pipeline

Inventory, then this design, then the package, then the tests. The producer stops at `OPTICS_PKG02_UNIT_C_READY_FOR_COUNCIL`. Merge and writer activation stay closed.

## Flow

1. Deep-copy the input. The caller's object and any on-disk file stay as they were.
2. Present that copy to `validate_evidence` from `@vantio/optics-evidence-contract`. Run logs use the public mapper. A bare call renames `hostname`, `status`, `opticsStatus`, `applicationStatus`, and `ts` onto contract names before validation. Envelope fragments rename `trace_id` to `run_id`, `pid` to `process_id`, `ppid` to `parent_process_id`, and `ts` to `started_at`, then validate as `run_envelope`. A CLI identity fragment with no call stores `optics_status` `UNAVAILABLE`. `generated_at` is not stored as `ended_at` in the scored projection.
3. Project the mapper record onto the Unit A declared canonical object.
4. Return the projection, the reader label, and diagnostics. Discard the projection with the process. Nothing is appended to a run directory.

## Projection rules

- Live `opticsStatus` `SUCCESS`, and any optics token outside the enum, become `UNAVAILABLE` with `OPTIMISTIC_DEFAULT_FORBIDDEN`. Explicit `optics_status` `OBSERVED` stays `OBSERVED`.
- Missing optics status on an observation is `UNAVAILABLE`.
- An empty CLI `calls` array is `optics_status` `NOT_OBSERVED` plus `call_count` `0`. A missing file and an empty `shield()` are `UNAVAILABLE`. Corrupt JSON and unreadable bytes are `OPTICS_ERROR` and emit no record.
- Legacy `bytes` `0` is `response_bytes` null. Explicit `response_bytes` `0` stays `0`. A missing byte count omits the key.
- `failure_kind` `none` is omitted. Transport `error` `network_error` is omitted. A transport `error_class` stays in the diagnostic. `failure_kind` `wrapped` keeps `error_class` and `issue_location` `CUSTOMER_APPLICATION`.
- Invalid `method` and invalid `sampling` are omitted. `sampling` is not rewritten to `UNSAMPLED` in the scored object.
- A comma-joined `mediation` is the reading `unknown`. It is one field. It does not become extra events.
- `+00:00` timestamps normalize to `Z` with three fractional digits on the copy only.
- Mixed per-call application tokens set envelope `lifecycle` `PARTIAL`. They do not set `application_status` `PARTIAL`.
- `duration_ms` `0` with null HTTP status is pre-completion: the duration is omitted and `lifecycle` is `INTERRUPTED`.
- Inherited `trace_id` without the witness becomes `run_id` and `trace_id_basis` `ASSERTED_CONTEXT`.
- A witness plus a recognized producer and a version yields `trace_id_basis` `OPTICS_GENERATED`. The witness value is absent from the projection.
- `IMPORTED` keeps `original_evidence_origin`. Claimed `LOCAL_OBSERVATION` without producer and version is the reader label `LEGACY_UNMARKED` and is not stored as local.
- Node SDK 0.2.4 ingest is `UNSUPPORTED` and emits no local record.
- A `future_not_shipped` input still projects. `unsupported_state` is `UNSUPPORTED` because a frozen reader is outside this adapter.

## Package identity

`vantio-optics-python-adapter` `0.0.0-unstable-pre-1.0`. That name is not the 3.1.0 distribution name `vantio-agent-sdk`.
