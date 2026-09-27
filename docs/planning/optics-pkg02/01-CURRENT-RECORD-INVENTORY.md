# Optics PKG-02 — current record inventory

Audience: INTERNAL_RESTRICTED

Method: this inventory was read from source at `dc212bca61fe80b65bb2cbab8e8f812c035ff2e0`. Docs were compared after the source read. Tests were read where they lock a token. No live writer was executed and no file outside this directory was edited.

The row-level classification of all 120 catalog rows and 67 compatibility names is `RECORD-VOCABULARY.json`. This file is the source map those rows cite.

## 1. Surfaces

| # | Surface | Writer or reader | Symbol | Persists a local evidence record |
| --- | --- | --- | --- | --- |
| 1 | CLI run log | Writer | `process.on("exit")` in `packages/vantio-cli/bin/interceptor.cjs` | Yes. `~/.vantio/runs/<trace>.json` |
| 2 | Node SDK | Writer of context only | `withVantio` / `shield` and `reportAnomaly` in `packages/vantio-agent-sdk/src/index.ts` | No local run log. Optional ingest POST. |
| 3 | Python SDK | Writer | `_record` and `_write_run_log` in `packages/vantio-agent-sdk-py/vantio/_http_observe.py` | Yes, only when `_calls` is non-empty |
| 4 | Shared display helper | Reader and labeler | `displayCall`, `rollupCalls`, `withSchema` in `packages/vantio-cli/bin/optics-cx.cjs` | No |
| 5 | Run log | Both envelopes | `vantio_run_log: "1"` | Yes |
| 6 | Per-call row | Both | CLI `_calls.push`; Python `_record` | Yes, inside `calls` |
| 7 | Structured CLI output | Writer to stdout | `writeRunJson`, `proofJson`, discover, search, tail, diff, demo, status in `packages/vantio-cli/bin/vantio.js` | Demo also writes a run file |
| 8 | Human-readable | Reader | CLI stderr `logFreeObservation`, HTML and Markdown prove, Python `customer_view_lines` | No |
| 9 | Proof | Reader | `proofJson`, `generateHtmlReport`, `generateMarkdownReport`; MCP `proveMarkdown` | No |
| 10 | Test and fixture | Reader of locked behavior | `packages/vantio-cli/test/optics-cx.test.js`; `packages/vantio-agent-sdk-py/tests/test_optics_status.py`; `tests/optics-evidence-contract/corpus.json` | PKG-01 corpus is not a live run log |
| 11 | Demo | Writer | `demoCommand` | Yes. Host `optics-demo.invalid` |
| 12 | Product health | Not a contract record | `statusCommand`, `sdkRows` | No `product_health` record |
| 13 | Product telemetry | Writer | `sendTelemetry` in `packages/vantio-cli/bin/telemetry.cjs`; `send_telemetry` in `vantio/_telemetry.py` | No. Opt-in POST. Off unless `VANTIO_TELEMETRY=1` |

`packages/vantio-optics-mcp/src/runs.js` is a reader. It keeps files whose `vantio_run_log` is `"1"`, skips corrupt JSON, and reads `log.machine` even though neither writer stores `machine`.

## 2. CLI run log

Writer: the exit handler builds `log` and `writeFileSync`s it. The write is attempted on every process exit, including zero calls. Failure is swallowed.

Envelope keys actually written:

`vantio_run_log`, `schema_version` `2`, `plane`, `data_note`, `trace_id`, `pid`, `ppid`, `node_version`, `platform`, `arch`, `started_at`, `generated_at`, `duration_ms`, `cli_version`, `free_mode`, `calls`, `summary`, `residual`.

There is no `schema_status`, `runtime`, `evidence_origin`, `record_type`, or `optics_status` on this file.

`trace_id` comes from `VANTIO_TRACE_ID` or `0x` plus 16 hex characters from a UUID. That string is a run identifier. PKG-01 maps it to `run_id`, not to contract `trace_id`.

`started_at` and `generated_at` use `Date.toISOString()` (UTC `Z`, millisecond precision). `duration_ms` is `Date.now()` minus `_startMs`.

Per-call keys actually persisted, from the exit `.map`:

`hostname`, `provider`, `method`, `path`, `scheme`, `request_bytes`, `bytes`, `status`, `ok`, `content_type`, `duration_ms`, `action`, `ts`, `redactions`, `error`, `error_class`.

`mediation` may exist on the in-memory object and is dropped here. `bytes` is `call.bytes || 0`, so `null` and `undefined` become `0`. `provider` falls back through `guessProvider`. `redactions` falls back to `0`.

`summary.total_bytes` sums `x.bytes || 0` before that map. `summary.est_spend_usd` is `null` in free mode and a number otherwise. `summary` also carries `total_calls`, `hosts`, `providers`, `errors`, `by_host`, `by_provider`, `redacted`, and `blocked`.

Fetch free-tier path (`wrapFetch`) stores `bytes: null` when the response has no content-length, then the exit map replaces that with `0`. Undici free-tier path stores `0` immediately when content-length is absent. Undici `applyDispatchGate` `baseCall` stores `bytes: 0`, `status: null`, `ok: true`, and `duration_ms: 0` before the response exists.

`extractRequestMeta` keeps `pathname` only. Query strings are not stored. `responseMeta` keeps the media type before `;`.

Actions observed in `_calls.push`: `OBSERVED` on the free path; `ALLOWED`, `REDACTED`, `BLOCKED_HOST`, `BLOCKED_SIZE`, `BLOCKED_SPEND`, `DRY_RUN_BLOCKED_HOST`, `DRY_RUN_BLOCKED_SIZE`, `DRY_RUN_BLOCKED_SPEND` on paid paths.

## 3. Node SDK

`@vantio/agent-sdk` `0.2.4` `shield` stores a `traceId` in `AsyncLocalStorage`. The default is `randomUUID()`. Nothing in `src/index.ts` writes `~/.vantio/runs`.

`reportAnomaly` POSTs `{ traceId, auditMode, eventPayload }` to `/api/v1/ingest` only when an ingest URL and cloud ingest are enabled. `eventPayload` fields are `bytes_severed`, `pid`, `timestamp_ns`, `target_host`, and `action_taken`. `timestamp_ns` is a number of nanoseconds, not an RFC3339 string. `action_taken` includes enforcement tokens. The example in the same file names `SEVERED`, which is not in the `VantioActionTaken` union.

Every catalog field is `MISSING_IN_NODE` for this package. The live Node record writer is the CLI interceptor, not this SDK.

## 4. Python SDK

`_write_run_log` returns immediately when `_calls` is empty or `_trace_id` is missing. An empty `shield()` does not create a run file. `empty_observation()` is an in-memory view with `opticsStatus` `NOT_OBSERVED`. It is not that file.

Envelope keys:

`vantio_run_log`, `schema_version` `2`, `schema_status` `unstable-pre-1.0`, `plane`, `workflow` `sight_loop`, `data_note`, `status_labels`, `trace_id`, `runtime` `python`, `mediation` (comma-joined tokens), `started_at`, `generated_at`, `calls`, `summary`, `residual`.

No `pid`, `ppid`, `platform`, `arch`, `duration_ms`, or SDK version on the envelope.

`started_at` and `generated_at` and per-call `ts` use `datetime.now(timezone.utc).isoformat()`, which is `+00:00` with microseconds. Socket `duration_ms` uses `time.perf_counter`. HTTP `duration_ms` uses `time.time`. Both are integer milliseconds, floored at 0.

`_record` always sets `opticsStatus` to `SUCCESS`, then `applicationStatus` from the HTTP code, then `opticsLabel`, then `apply_customer_outcome`. `tests/test_optics_status.py` and `tests/test_outcome_clarity.py` lock `opticsStatus == "SUCCESS"` for recorded calls, including an unavailable provider outcome. `tests/test_outcome_clarity.py` locks `empty_observation().opticsStatus == "NOT_OBSERVED"`.

`_rollup_status` returns `NOT_OBSERVED` / `NOT_OBSERVED` for an empty list, and `SUCCESS` plus either one application token or `PARTIAL` otherwise. `PARTIAL` is not a member of contract `application_status`.

`_account_response_bytes` adds content-length to a spend counter. It does not set a byte field on the call. Subprocess observation stores `bytes_observed`.

`failure_kind` is stored for classified exceptions. A final HTTP status wins over a nested transport error. `error` `network_error` is set only when the kind is not `wrapped`.

urllib method is `POST` when a body is present and `GET` otherwise. Path comes from `urlparse` and does not include the query. Port is parsed and is not passed into `_record` on that path.

Python `schema_status` on the envelope matches the contract constant. Python `schema_version` `2` does not. The contract stores `0`.

## 5. Display, structured output, and proof

`optics-cx.cjs` `opticsStatusForRecordedCall` returns `SUCCESS` for every call. `rollupCalls` returns `NOT_OBSERVED` / `NOT_OBSERVED` when `calls` is empty, and `SUCCESS` plus one application token or `PARTIAL` otherwise. `applicationStatusFromHttp` ignores `ok`. `packages/vantio-cli/test/optics-cx.test.js` locks that a call with `status` 500 and `ok` true still displays `opticsStatus` `SUCCESS` and `applicationStatus` `APPLICATION_ERROR`.

`humanStatus("SUCCESS")` is `Successful`.

Structured stdout uses `withSchema`, which adds `schema_status` `unstable-pre-1.0` to the JSON document. That key is not on the CLI run file.

| Command | optics token behavior read from source |
| --- | --- |
| `run --json` | `opticsStatus` `SUCCESS`, or `OPTICS_ERROR` when the child died by signal. `applicationStatus` is always `NOT_OBSERVED` on this document. |
| `prove --json` | Rollup from `rollupCalls`. Calls projected by `publicCall`. |
| `discover --json` | Both optics and application are `SUCCESS` when any host row exists, else both `NOT_OBSERVED`. |
| `search --json` | Optics `SUCCESS` when any hit exists, else `NOT_OBSERVED`. Application comes from the HTTP rollup. |
| `tail --json` | Rollup of the shown slice. |
| `diff --json` | No optics token. Byte totals use `call.bytes \|\| 0`. |
| `demo --json` | `opticsStatus` and `applicationStatus` from `displayCall` of a stub with HTTP 200. The stub file stores `bytes: 0`. |
| `status --json` | The same token set describes install, registry, telemetry, directory bytes, run-log presence, and whether a provider SDK package resolves. Telemetry's token is `SUCCESS` whenever the posture object was built. `sdkRows` uses `SUCCESS` or `UNSUPPORTED` for importability. |

HTML and Markdown proof use the same rollup. MCP `proveMarkdown` prints `action`, not `opticsStatus`, and prints `log.machine`.

Corrupt CLI JSON is reported by `failUnreadable` on prove, discover, and search paths that call it. MCP `listRunLogs` skips corrupt files with an empty catch. A skip is not a `NOT_OBSERVED` record and it is not a success record. This plan does not change the MCP.

## 6. Docs compared with source

`docs/internal/optics-pkg01/COMPATIBILITY.md` describes the contract mapper: legacy `trace_id` becomes `run_id`, legacy `bytes` `0` becomes `response_bytes` null, and missing origin becomes `LEGACY_UNMARKED`. That is reader behavior inside the private package. The live CLI writer still stores `bytes || 0`. Both statements are true of different programs.

`docs/internal/optics-pkg01/FIELD-CATALOG.md` says 120 field rows. `field-catalog.json` has 120 rows and 88 unique names. This inventory uses that count.

`docs/architecture/optics-foundation/08-ARCHITECTURE-DECISION-PACK.md` section 37 says the Node exit mapper stores `call.bytes || 0`. The exit map at interceptor line 3736 matches that sentence.

PKG-01 notes that say the package is not imported by the live CLI or Python SDK match `contract-metadata.json` (`loaded_by_live_cli_0_3_24` false, `loaded_by_python_3_1_0` false). This force did not add an import.

## 7. Catalog classification

Canonical rows: 120. Unique names: 88. Rows absent from both live run logs: 88.

CLI class counts on the 120 rows:

| Class | Count |
| --- | --- |
| `EXACT_MATCH` | 10 |
| `NAME_ONLY_MATCH` | 9 |
| `SEMANTIC_MISMATCH` | 6 |
| `TYPE_MISMATCH` | 0 |
| `OPTIMISTIC_DEFAULT` | 2 |
| `MISSING_IN_NODE` | 93 |
| `MISSING_IN_PYTHON` | 0 on the CLI column |
| `LEGACY_ONLY` | 0 on catalog rows |
| `READER_ONLY` | 0 on catalog rows |
| `PROHIBITED_BY_PKG01` | 0 on catalog rows |
| `UNKNOWN` | 0 |

Python class counts on the same 120 rows:

| Class | Count |
| --- | --- |
| `EXACT_MATCH` | 8 |
| `NAME_ONLY_MATCH` | 5 |
| `SEMANTIC_MISMATCH` | 8 |
| `TYPE_MISMATCH` | 0 |
| `OPTIMISTIC_DEFAULT` | 1 |
| `MISSING_IN_NODE` | 0 on the Python column |
| `MISSING_IN_PYTHON` | 98 |
| `UNKNOWN` | 0 |

`TYPE_MISMATCH` is used on the compatibility name `timestamp_ns` (nanoseconds versus RFC3339), not on a catalog row. `UNKNOWN` was not needed. Every catalog row was classified from the writer source above.

Pairs that are not "missing on both sides":

| CLI class | Python class | Rows |
| --- | --- | --- |
| `EXACT_MATCH` | `MISSING_IN_PYTHON` | `run_envelope.platform`, `run_envelope.arch`, `run_envelope.duration_ms`, `observation_event.request_bytes`, `observation_event.content_type` |
| `SEMANTIC_MISMATCH` | `SEMANTIC_MISMATCH` | `run_envelope.schema_version`, `run_envelope.trace_id`, `run_envelope.ended_at`, `observation_event.provider_id`, `observation_event.action` |
| `MISSING_IN_NODE` | `EXACT_MATCH` | `run_envelope.schema_status`, `run_envelope.runtime`, `observation_event.failure_kind`, `observation_event.mediation` |
| `NAME_ONLY_MATCH` | `MISSING_IN_PYTHON` | `run_envelope.process_id`, `run_envelope.parent_process_id`, `run_envelope.runtime_version`, `run_envelope.cli_or_sdk_version` |
| `NAME_ONLY_MATCH` | `NAME_ONLY_MATCH` | `run_envelope.run_id`, `run_envelope.call_count`, `observation_event.destination_host`, `observation_event.http_status` |
| `EXACT_MATCH` | `EXACT_MATCH` | `observation_event.scheme`, `observation_event.path`, `observation_event.error_class` |
| `EXACT_MATCH` | `SEMANTIC_MISMATCH` | `run_envelope.started_at`, `observation_event.method` |
| `MISSING_IN_NODE` | `NAME_ONLY_MATCH` | `observation_event.application_status` |
| `NAME_ONLY_MATCH` | `SEMANTIC_MISMATCH` | `observation_event.started_at` |
| `OPTIMISTIC_DEFAULT` | `MISSING_IN_PYTHON` | `observation_event.response_bytes` |
| `OPTIMISTIC_DEFAULT` | `OPTIMISTIC_DEFAULT` | `observation_event.optics_status` |
| `SEMANTIC_MISMATCH` | `EXACT_MATCH` | `observation_event.duration_ms` |

The other 88 rows are `MISSING_IN_NODE` and `MISSING_IN_PYTHON`. They are listed in `RECORD-VOCABULARY.json` with `missing_in_both_live_writers` true. They include every `derived_diagnostic`, `annotation`, `product_health`, `import_quarantine`, and `validation_result` field, plus the envelope and event fields neither writer stores (`evidence_origin`, `issue_location`, `clock_quality`, `lifecycle`, trace basis, session, producer identity, and the rest of that set).

Node SDK class on all 120 catalog rows: `MISSING_IN_NODE`.

## 8. Compatibility names

67 names are in `RECORD-VOCABULARY.json` with `role` `compatibility`. Counts:

| Class | Count |
| --- | --- |
| `LEGACY_ONLY` | 15 |
| `NAME_ONLY_MATCH` | 13 |
| `SEMANTIC_MISMATCH` | 11 |
| `PROHIBITED_BY_PKG01` | 15 |
| `OPTIMISTIC_DEFAULT` | 5 |
| `READER_ONLY` | 5 |
| `TYPE_MISMATCH` | 1 |
| `MISSING_IN_NODE` | 2 |

The two `MISSING_IN_NODE` compatibility rows are `unicode_profile_id` and `unicode_profile_version`. Both live writers omit them. The pinned values are `PKG01-UCD-16.0.0` and `16.0.0` on the validation diagnostic, from `contract/unicode-profile-metadata.json`.

Prohibited names that live writers already emit include `plane`, `data_note`, `residual`, `free_mode`, `workflow`, `status_labels`, and `est_spend_usd`. The contract strips them. This plan does not delete them from CLI 0.3.24 or Python 3.1.0.
