# PKG-02 Unit B design

PRIVATE | INERT | NOT SHIPPED | NO LIVE WRITER | NO LIVE READER | NO MIGRATION | NO STABLE SCHEMA

Audience: INTERNAL_RESTRICTED

The adapter is `@vantio/optics-node-adapter`. `adaptNodeCopy` passes a value the caller already holds to `validateEvidence` or `validateBytes`. Those functions copy the value before they map it. `adaptFixture` builds that copy from a Unit A fixture declaration, then uses the same path.

The copy is discarded by the caller. The adapter has no writer, no path argument that reads a run file, and no export that activates Units D or E.

## How a fixture becomes a copy

Unit A stores an envelope and a call separately. The adapter joins them on the copy:

- A `vantio_run_log` envelope keeps its runtime. A Python envelope stays a Python-shaped copy so the same mapper scores it. This package does not edit Python `3.1.0`.
- A call with no envelope becomes `calls: [call]` on a `vantio_run_log` `"1"` copy.
- Envelope `ts` is copied to `started_at` and the alias key is removed on the copy.
- A witnessed envelope is passed as `record_type` `run_envelope` with `trace_id_basis` `OPTICS_GENERATED` and the fixture's version placeholder. The witness value is not copied onto the detached result.
- Node SDK ingest and future-only extra fields are not passed to the mapper. The result is `UNSUPPORTED`, `record_emitted` false, and `optics_health` `UNAVAILABLE`.

Absent files and unreadable paths do not open a filesystem path. Malformed text is passed to the mapper as text.

## Detached reading

The mapper result is the mechanism. The detached reading then applies the merged Unit A rules where the mapper output would disagree with those rules:

- `optics_status` `SUCCESS` becomes `UNAVAILABLE`, with `optimistic_default_forbidden` true. Explicit `OBSERVED` stays.
- An unknown optics token stays `UNAVAILABLE` and sets the same flag. The raw token is not stored.
- Invalid `sampling` is omitted. It is not left as `UNSAMPLED`.
- An invalid method that the mapper stored as `unknown` is omitted.
- `failure_kind` `none` is omitted.
- Comma-joined `mediation` is omitted.
- Legacy `trace_id` stays `run_id` with `trace_id_basis` `ASSERTED_CONTEXT`. It is not canonical `trace_id` and not `OPTICS_GENERATED`.
- `IMPORTED` is written back onto the detached record with `original_evidence_origin` when that value is an allowlisted token. It is not upgraded to `LOCAL_OBSERVATION`.
- A span the source omitted stays omitted. A source `span_id` null stays null.
- `generated_at` may appear as `ended_at` because the mapper maps that alias. The diagnostic says that value is file write time.
- Pre-completion `duration_ms` `0` with null HTTP status omits the duration and sets `lifecycle` `INTERRUPTED`.
- Two application tokens `SUCCESS` and `APPLICATION_ERROR` set envelope `lifecycle` `PARTIAL`. They do not set `application_status` `PARTIAL`.
- An explicit empty `calls` array is `optics_health` `NOT_OBSERVED`. A missing file is `UNAVAILABLE`. Corrupt or unreadable input is `OPTICS_ERROR`.

`live_writer_modified` stays false. `schema_version` on the detached record is `0`. Legacy `2` remains `compatibility.legacy_schema_version`.
