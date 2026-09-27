# Optics PKG-02 — shared record vocabulary

Audience: INTERNAL_RESTRICTED

This vocabulary is the planning contract for a future Node writer and a future Python writer. It is not a stable schema. `schema_status` stays `unstable-pre-1.0`. `schema_version` stays `0`. JSON Schema is not the source of truth. The field source of truth is `packages/optics-evidence-contract/contract/field-catalog.json` at the starting commit. `RECORD-VOCABULARY.json` repeats every catalog row and every compatibility name with the attributes this force requires.

PKG-02 does not add fields for usage, cost, token counts, machine hostname, a new annotation origin, or freshness `CURRENT`.

## 1. Record classes

Future records use the catalog classes: `run_envelope`, `observation_event`, `derived_diagnostic`, `annotation`, `product_health`, `import_quarantine`, and `validation_result`. `proof_manifest` stays unwitnessed by this slice.

A live `vantio_run_log` file is not yet one of those classes. A future adapter may interpret it. It must not rewrite it.

## 2. Identity

| Canonical name | Definition locked here | Live key | Absent behavior |
| --- | --- | --- | --- |
| `run_id` | One wrapped execution boundary. Charset `^[A-Za-z0-9_-]{1,80}$`. | Envelope `trace_id` | Omit. Do not copy it into `trace_id`. |
| `parent_run_id` | Explicit parent only. | Absent | Omit, or null when the writer truly has no parent and says so. |
| `trace_id` | Validated trace context. Not a synonym for `run_id`. | The live string is the run id | Do not store the live run string here. |
| `trace_id_basis` | Required when `trace_id` is present. | Absent | Inherited context is `ASSERTED_CONTEXT`, meaning `ASSERTED_CONTEXT_NOT_OBSERVATION_PROOF`. |
| `span_id`, `parent_span_id` | Null on the envelope. Hex on an event when present. | Absent | Envelope stays null. Do not invent a span. |
| `session_id` | Optional group. Never a metric label. Max 80 UTF-8 bytes. Not truncated. Not rewritten to NFC. | Absent | Omit both session fields. |
| `session_id_basis` | Required when `session_id` is present. | Absent | Omit with the session id. |
| `event_id` | Derived from `producer_id` and `producer_sequence` when both exist. | Absent | Do not mint an id that pretends a sequence existed. |
| `producer_id`, `producer_sequence`, `sequence` | Producer order. `sequence` equals `producer_sequence`. | Absent | Omit. A conflict is `identity_conflict` `PRODUCER_SEQUENCE`, not a success. |
| `identity_conflict` | `NONE`, `PARENT`, or `PRODUCER_SEQUENCE`. | Absent | Omit. Do not store `NONE` to hide a missing parent. |

`OPTICS_GENERATED` for a trace requires producer, version, and witness `PKG01_OPTICS_GENERATED_WITNESS` on input. The witness is not copied into the stored record. A CLI `0x` id and a Python `uuid4` are run ids. They are not evidence that Optics generated a W3C trace.

## 3. Process

| Canonical name | Definition | Live fact |
| --- | --- | --- |
| `process_id` | Integer or null. | CLI `pid`. Python omits it. |
| `parent_process_id` | Integer or null. | CLI `ppid`. Python omits it. |
| `runtime` | `node` or `python`. | Python stores `python`. CLI stores `node_version` and omits `runtime`. |
| `runtime_version` | Version token, max 32. | CLI `node_version`. Python omits it. |
| `platform`, `arch` | Closed enums. | CLI stores `process.platform` and `process.arch`. Python omits both. |
| `producer` | `node_interceptor`, `python_observe`, or `demo_command`. | Neither live envelope stores it. |
| `cli_or_sdk_version` | Version token. | CLI `cli_version`. Python omits it. |

A recognized producer plus a version token is part of provenance. Without them, a claimed `LOCAL_OBSERVATION` stays reader label `LEGACY_UNMARKED`.

Process propagation is off in this slice (`process_propagation_in_slice` false). PKG-02 does not start inheriting process identity across a spawn boundary.

## 4. Time

`started_at` and `ended_at` are RFC3339 UTC. The contract accepts `Z` or `+00:00` and stores `Z` with exactly three fractional digits. A non-zero offset is rejected, not converted.

CLI `toISOString()` already matches the stored form. Python `isoformat()` is `+00:00` with microseconds. A future Python writer stores the contract form. This plan does not change Python 3.1.0.

`generated_at` is file-write time. Mapping it to `ended_at` is an adapter courtesy. It is not proof the workload ended at that instant. Future writers that know the run end store `ended_at` from that instant and may keep `generated_at` only as a read alias until a reader matrix drops it.

`duration_ms` is an integer count of milliseconds, or absent. `0` is a measured zero only after the interval completed. CLI undici dispatch stores `0` before completion. That `0` is not a measured duration. Future writers omit `duration_ms` until the interval ends.

`clock_quality` is `MONOTONIC`, `WALL_CLAMPED`, or `UNAVAILABLE`. Neither writer stores it. Wall `Date.now` / `time.time` and socket `perf_counter` are different clocks. Future writers set `clock_quality` from the clock they used. They do not pick `MONOTONIC` for a wall clock.

`lifecycle` is `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, or `RECOVERED`. It is not `optics_status` and not `application_status`. Neither writer stores it. A future interrupted run stores `INTERRUPTED` and does not store `optics_status` `SUCCESS`.

## 5. Destination and provider

`destination_host` is the registry host. Live key: `hostname`. DNS names are lowercased. IPv6 brackets are removed. Default ports are not stored. An explicit port is `destination_port`. Live writers parse port for scope and then drop it. Future writers store an explicit port and omit a default port.

`scheme` is `http`, `https`, `ws`, `wss`, or `unknown`. `method` is the closed HTTP set or `unknown`. `path` is path only, max 512 UTF-8 bytes, not truncated. Query, fragment, and userinfo are stripped. If they cannot be separated, destination fields are omitted. Database connection strings omit destination fields.

`provider_id` is an allowlisted token or `unknown`. `provider_confidence` is `CATALOG`, `REGIONAL_PATTERN`, `LOCAL_OLLAMA`, or `NONE`. Confidence `NONE` forces `provider_id` `unknown`. Live `provider` strings from `guessProvider` and `resolve_provider` are not promoted. `LOCAL_OLLAMA` requires host `localhost`, `127.0.0.1`, or `::1` and port `11434`.

`mediation` is one closed token or `unknown`. A comma-joined Python envelope string is not one token. Future envelopes store one token per event. The envelope does not join them with commas.

Redirect hops are not separate live events. Fetch and urllib record the final status against the request host. PKG-02 does not invent redirect records. A future writer that observes a hop uses the contract redirect destination inputs and still strips query and userinfo. It does not call a 3xx a success by omitting it.

## 6. Outcome dimensions

These dimensions stay separate. A reader must not collapse them into one bit.

| Dimension | Canonical home | Tokens that belong here | What it is not |
| --- | --- | --- | --- |
| Optics machinery | `optics_status` | `OBSERVED`, `NOT_OBSERVED`, `UNSUPPORTED`, `UNAVAILABLE`, `APPLICATION_ERROR`, `OPTICS_ERROR`, `PARTIAL`, `SUCCESS` | Not the workload result |
| Workload | `application_status` | `SUCCESS`, `APPLICATION_ERROR`, `UNAVAILABLE`, `NOT_OBSERVED` | `PARTIAL` is not in this enum |
| Provider HTTP | `http_status` | Integer 100–599 or absent | Not `ok`. Not `0`. Not `200` by default |
| Transport class | `failure_kind` | `dns`, `connection`, `tls`, `timeout`, `network`, `wrapped`, `none` | Not the string `network_error` |
| Exception type | `error_class` | Token of letters, digits, underscore, length 1–64 | Not an error message |
| Where the issue sits | `issue_location` | `NONE`, `OPTICS`, `CUSTOMER_APPLICATION`, `PROVIDER_INTERACTION`, `NETWORK`, `ENVIRONMENT`, `CONFIGURATION`, `COVERAGE`, `UNKNOWN` | Not a fault label. `Provider fault` is forbidden |
| Attempt completeness | `lifecycle` | `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, `RECOVERED` | Not mixed-call `PARTIAL` |
| Coverage | `coverage_note` | `WRAPPED_PROCESS` | Not residual prose |
| Derived phrases | `derived_diagnostic` | Fixed `application_outcome_label` and `provider_response_phrase` | Not Python free-form sentences |
| Product health | `product_health` | Closed `name` values | Not `vantio status` JSON |
| Store integrity | `integrity_state` | `OK`, `FAILED`, `UNKNOWN` | Not Optics `SUCCESS` |
| Completeness | `completeness_impact` | Catalog completeness tokens | `scope_complete` stays false |

`action` on an observation is the constant `OBSERVED` or it is omitted. `ALLOWED`, `REDACTED`, `BLOCKED_*`, and `DRY_RUN_BLOCKED_*` are enforcement actions. The contract drops those records with `ENFORCEMENT_ACTION_EXCLUDED`. Future Optics writers do not store them as observations. Phantom Engine remains the enforcement product. This plan does not remove those tokens from CLI 0.3.24 or Python 3.1.0.

`SUCCESS` remains a readable `optics_status` token because it is in the frozen catalog enum and in the live display vocabulary. It is not the future writer's default for "a call was recorded." The future writer stores `OBSERVED` for a locally observed call. `SUCCESS` on `application_status` means the HTTP code was 200–399, which includes redirects. That is the workload dimension. The human gloss `Successful` must not be the only place a customer can see which dimension fired. Display keeps the machine token beside the gloss.

`PARTIAL` on a live run summary means the calls did not share one application token. Future run records express that mix as `lifecycle` `PARTIAL` or as distinct per-call `application_status` values plus a derived label `Partial`. They do not store `application_status` `PARTIAL`.

`issue_location` is computed by the validator from HTTP class, network-without-HTTP, a wrapped exception, coverage evidence, configuration, and environment. `NONE` is for an HTTP 2xx/3xx observation that has no other fault. `NONE` is not a fill for a rejected record. `UNKNOWN` stays `UNKNOWN`.

`ok` is a legacy boolean. Readers ignore it, matching `applicationStatusFromHttp`. A future writer does not emit `ok`.

## 7. Evidence quality

Writer origins: `LOCAL_OBSERVATION`, `SIMULATED_DEMO`, `IMPORTED`, `TEST_FIXTURE`, `PRODUCT_HEALTH`, `DERIVED_DIAGNOSTIC`.

`LEGACY_UNMARKED` is a reader label. It is not stored as a writer origin. Missing origin becomes that label. A claimed `LOCAL_OBSERVATION` without recognized producer, version, and provenance also becomes that label. Demo host `optics-demo.invalid` on an observation is `SIMULATED_DEMO` even when the file omitted origin. The envelope builder does not treat the whole file as a demo from that host. A demo file's envelope stays unmarked unless a future demo writer sets `producer` `demo_command` and origin `SIMULATED_DEMO` on purpose. It must not use `LOCAL_OBSERVATION`.

Imports store `evidence_origin` `IMPORTED` and preserve `original_evidence_origin`. They do not upgrade maturity. Annotations use `annotation_role` `CUSTOMER_ANNOTATION` and refuse an evidence origin.

`sampling` is the constant `UNSAMPLED`. The contract fills it when absent. Future writers emit it so absence is not the only signal. The fill is not a success claim.

`call_count` is the number of child events the validator accepted into the envelope, and the contract also overwrites it from `calls.length`. Live `summary.total_calls` is the alias. `dropped_count` is a separate integer. Silence on an out-of-scope host is not a dropped event and not a success. Future writers do not invent events for traffic they did not wrap. They may set `coverage_note` `WRAPPED_PROCESS` on a run that was wrapped. They do not treat residual prose as that enum. `plane`, `data_note`, `residual`, `workflow`, `status_labels`, and `free_mode` stay prohibited.

`calls` longer than 64 hit `INPUT_BOUND` and the envelope is dropped. A future adapter reports that bound. It does not keep the first 64 and call the run complete. PKG-02 does not raise 64.

Corrupt input is not an empty valid record. Validator faults and malformed JSON reject the record, set issue location `OPTICS` when the fault is internal, and return the caller application result detached. A reader that cannot open a file reports `UNAVAILABLE` or `OPTICS_ERROR`. It does not report `NOT_OBSERVED`. `NOT_OBSERVED` means the wrap ran and no supported call was stored.

`scope_complete` stays false. Completeness tokens stay visible. `integrity_state` on a validation result stays `UNKNOWN` until a store exists. This packet does not create that store.

## 8. Versioning and Unicode

`record_type` is the class constant. `schema_status` is `unstable-pre-1.0`. Any other status string is corrected and reason `SCHEMA_STATUS_CORRECTED` is recorded. `schema_version` on the contract record is `0`. Live integer `2` is kept only as `compatibility.legacy_schema_version`.

Unicode profile identity is diagnostic, not a new allowlisted payload field: `unicode_profile_id` `PKG01-UCD-16.0.0`, `unicode_profile_version` `16.0.0`. Privacy decisions use the pinned tables. They do not consult host ICU or CPython `unicodedata`. Future conformance runs compare canonical JSON across Node and Python against that profile. This plan does not regenerate the tables.

## 9. Privacy, metrics, and deprecation

Sensitivity classes stay the catalog values: `STRUCTURAL`, `IDENTITY`, `DIAGNOSTIC`, `CUSTOMER_TEXT`. High-cardinality identity is not a metric label (`run_id`, `trace_id`, `session_id`, `event_id`). Export and proof eligibility stay the catalog booleans. Proof of a legacy file is a read of that file. It is not a rewrite into a proof manifest. `proof_manifest` stays out of this slice.

Aliases in `RECORD-VOCABULARY.json` stay readable. PKG-02 removes none of them. Removal waits for a later versioned release and a reader matrix that still shows the alias.

Customer text exists only on `annotation.text`, scanned, not truncated, rejected when it matches a detector. Observations do not gain a text field.

## 10. Future writer behavior

A future writer:

- Stores canonical names.
- Leaves missing values missing, under the dispositions in `03-NODE-PYTHON-DELTA.md`.
- Sets `evidence_origin` only with provenance that the contract will accept.
- Copies caller objects. It does not retain them. This matches the PKG-01 detached-result rule.
- Does not import the contract into CLI 0.3.24 or Python 3.1.0.

Display may show a human label from the fixed tables. The machine token remains in the record. A label is not eligibility for a metric.
