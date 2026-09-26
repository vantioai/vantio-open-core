# A1 — Evidence and privacy contract

Classification: `OPTICS_FOUNDATION_A1_CONTRACT_READY`

Revision: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. Gate 2 stays reopened until a fresh council passes. This line is not a council pass.

Audience: INTERNAL_RESTRICTED

Schema status for every object in this contract: `unstable-pre-1.0`. This document does not declare a stable v1.

This contract is the canonical evidence model. Storage selection in A2 must implement this model. Storage does not define it.

## 1. Evidence classes

These classes stay distinct. A record of one class must not be presented as another.

| Class | What it is | Where it lives | Counted in customer AI activity |
| --- | --- | --- | --- |
| Observed | A supported call or an attached run, captured in-process | Operational observation records | Yes, when origin is `LOCAL_OBSERVATION` |
| Derived diagnostic | Labels, rollups, issue location, and next-action text computed from observation fields | Derived records, or a view. Not a second copy of the observation payload | No. Views may display them beside the observation |
| Annotation | Customer-entered name or note | Annotation store, separate from observation bytes | No |
| Simulated demo | `vantio demo` or an equivalent in-process stub | Observation-shaped record with origin `SIMULATED_DEMO` | No |
| Imported | Bytes that arrived from outside this machine’s observation path | Quarantine, then an imported record | No, until a future explicit rule says otherwise. This pack’s rule is no |
| Product health | Optics’ own counters: writes, drops, integrity, migration, redaction failures | Product-health records | No |
| Optional Vantio product telemetry | Anonymous aggregate ping | Separate channel and destination. Never the evidence store | No |
| Portable proof | Bounded export of a scoped observation set plus a manifest | Proof artifact, outside the mutable operational store | Display only. It is not a new observation |
| Fixture | Test-only records | Origin `TEST_FIXTURE`. Must not be written by production install paths | No |
| Unsupported / unavailable | Honest gaps: client not hooked, no HTTP status, registry not checked | Status tokens on a record or on a command result. Not an origin | They qualify an observation. They are not success |

`UNSUPPORTED` and `UNAVAILABLE` remain status tokens from `packages/vantio-cli/bin/optics-cx.cjs`. They are not evidence origins.

## 2. Evidence-origin values

Writers that persist evidence use exactly one of:

- `LOCAL_OBSERVATION`
- `SIMULATED_DEMO`
- `IMPORTED`
- `TEST_FIXTURE`
- `PRODUCT_HEALTH`
- `DERIVED_DIAGNOSTIC`

Rules:

- Missing origin is not `LOCAL_OBSERVATION`. Current files have no origin. Readers call that disposition `LEGACY_UNMARKED`. It is a reader state, not a seventh writer value.
- A reader preserves an allowlisted writer origin on a legacy file only when a recognized Optics producer and version supply sufficient provenance. Otherwise the reader disposition is `LEGACY_UNMARKED`. A claimed `LOCAL_OBSERVATION` without that provenance is `LEGACY_UNMARKED`. Preservation is not promotion.
- Recognized producers are `node_interceptor`, `python_observe`, and `demo_command`. Sufficient provenance requires all of: the legacy marker `vantio_run_log == "1"` or an operational-store row written by that producer; `producer` set to one of those three values; a producer version string present, at most 32 characters, charset `[A-Za-z0-9._+-]`; and `evidence_origin` equal to one of the six writer origins. The demo producer with destination `optics-demo.invalid` preserves `SIMULATED_DEMO` only. It does not preserve `LOCAL_OBSERVATION`.
- `LEGACY_UNMARKED` is excluded from operational trends and from any future baseline, the same way demo and fixture evidence are excluded. Default trend scope states that exclusion. Founder decision 6, whether an explicit customer promote may stamp `LEGACY_UNMARKED` as `LOCAL_OBSERVATION`, stays unresolved. No migration, import, or reader promotes evidence maturity on its own.
- A legacy file whose destination is `optics-demo.invalid` is `SIMULATED_DEMO` on read. It is not promoted to `LOCAL_OBSERVATION`.
- Import writes `evidence_origin` `IMPORTED`. It also stores `original_evidence_origin` as the allowlisted origin found in the imported bytes, or `LEGACY_UNMARKED` when that value is missing or not allowlisted. Import provenance (`source_label`, `content_sha256`, `imported_at`, `accepted`) is a separate field set. Import does not rewrite `original_evidence_origin` and does not write `LOCAL_OBSERVATION`.
- Product telemetry is not given an evidence origin inside the operational store because it is not stored there.
- Derived fields that today sit inside the Python call object (`applicationOutcomeLabel`, `nextAction`, and the summary human lines) are `DERIVED_DIAGNOSTIC` in this contract. A future writer may keep a copy beside the observation. It must not be required in order to trust the observation.
- Annotations use `annotation_role` `CUSTOMER_ANNOTATION`. They are not given a writer origin. A seventh origin is not added while Founder decision 7 is unresolved.

## 3. Issue location

Machine values, stored on diagnostics, observation events, and command results:

- `NONE`
- `OPTICS`
- `CUSTOMER_APPLICATION`
- `PROVIDER_INTERACTION`
- `NETWORK`
- `ENVIRONMENT`
- `CONFIGURATION`
- `COVERAGE`
- `UNKNOWN`

`NONE` means no failing layer was identified. A successful operation uses `NONE`. HTTP 2xx and HTTP 3xx use `NONE`.

Human labels:

| Machine value | Human label |
| --- | --- |
| `NONE` | None |
| `OPTICS` | Optics |
| `CUSTOMER_APPLICATION` | Customer application |
| `PROVIDER_INTERACTION` | Provider interaction |
| `NETWORK` | Local network path |
| `ENVIRONMENT` | Local environment |
| `CONFIGURATION` | Configuration |
| `COVERAGE` | Observation coverage |
| `UNKNOWN` | Unknown |

Human text uses “issue location.” It does not assign legal blame, negligence, or ownership of a vendor relationship. The words “Provider fault” are not a display label.

`PROVIDER_INTERACTION` means an unsuccessful HTTP response was observed. It does not mean the provider is at fault. The HTTP status remains on the event. Catalog confidence does not change this location: a 401, 429, or 500 is `PROVIDER_INTERACTION` whether or not `provider_confidence` is `CATALOG`.

`optics_status` `SUCCESS` means Optics stored the observation record. It does not mean the provider call succeeded, and it does not by itself set issue location. A stored HTTP 500 has `optics_status` `SUCCESS`, `application_status` `APPLICATION_ERROR`, and `issue_location` `PROVIDER_INTERACTION`. If the record was not stored, there is no observation row with `optics_status` `SUCCESS`.

One rule selects the value. First match wins.

1. Optics hook, persistence, read, migration, formatter, privacy, or other internal failure, including a queue or disk refusal on the Optics write path: `OPTICS`. This is product-health or command-result location when the observation row was not stored. A row that was stored keeps the call’s location from the later rules.
2. Typed DNS, connection, TLS, or transport timeout, and no HTTP status was observed: `NETWORK`.
3. HTTP status 400–599 was observed: `PROVIDER_INTERACTION`.
4. Customer-code exception and no HTTP status was observed: `CUSTOMER_APPLICATION`.
5. Unsupported or unobserved path, and the evidence shows that gap: `COVERAGE`.
6. Unsupported or unobserved path, and the evidence does not show the gap: `UNKNOWN`.
7. Configuration fault, including a `VANTIO_HOME` reader/writer split or two accepted trace contexts that disagree: `CONFIGURATION`.
8. A local-environment condition was identified, and the condition is not an Optics-internal failure: `ENVIRONMENT`.
9. HTTP 2xx or HTTP 3xx, or any other successful operation with no identified failure: `NONE`.
10. A failure was identified and no earlier rule names the layer: `UNKNOWN`.

If no rule matches, the value is `UNKNOWN`. There is no combined value. Disk pressure on an Optics write is rule 1, `OPTICS`. When the layer is not determined, the value is `UNKNOWN`.

The HTTP code remains the application outcome. Issue location does not replace `application_status`.

### 3.1 Architecture test plan — issue location

Specified for a future implementation Force. Not executed here. No evidence tier is assigned.

| Case | Required `issue_location` |
| --- | --- |
| Successful operation with no identified failure | `NONE` |
| HTTP 200 and HTTP 3xx | `NONE` |
| HTTP 401, HTTP 429, and HTTP 500 | `PROVIDER_INTERACTION`, human label “Provider interaction” |
| Typed DNS failure with no HTTP status | `NETWORK` |
| Customer-code exception with no HTTP status | `CUSTOMER_APPLICATION` |
| Optics write failure | `OPTICS` |
| Unsupported path with evidence of the gap | `COVERAGE` |
| Unsupported path without evidence of the gap | `UNKNOWN` |

Display text for these cases does not contain “Provider fault.”

## 4. Allowlisted persisted-field catalog

Deny by default. A writer may persist a field only if it appears in this catalog for that record type. Unknown keys are dropped before persistence. They are not stored beside the record “for later.”

Cardinality classes: `LOW` (safe as a metric label), `BOUNDED` (enumerable, limited label use), `HIGH` (event or trace only, never a metric label).

Privacy classes: `STRUCTURAL`, `IDENTITY`, `DIAGNOSTIC`, `CUSTOMER_TEXT`.

### 4.1 Record type `run_envelope`

| Field | Type | Cardinality | Privacy | Notes |
| --- | --- | --- | --- | --- |
| `record_type` | const `run_envelope` | LOW | STRUCTURAL | |
| `schema_status` | const `unstable-pre-1.0` | LOW | STRUCTURAL | Required |
| `schema_version` | integer | LOW | STRUCTURAL | Monotonic. Not a stability promise |
| `evidence_origin` | origin enum | LOW | STRUCTURAL | Required |
| `run_id` | string, max 80, charset `[A-Za-z0-9_-]` | HIGH | IDENTITY | One wrapped execution boundary. Not the per-call span |
| `parent_run_id` | string, max 80, charset `[A-Za-z0-9_-]`, or null | HIGH | IDENTITY | Set only from explicit parent context. Null when no parent run was supplied |
| `trace_id` | string, max 128, or null | HIGH | IDENTITY | Optional validated trace id. Not a synonym for `run_id` |
| `trace_id_basis` | enum in A4, or null | LOW | STRUCTURAL | Required when `trace_id` is present. Absent when `trace_id` is absent |
| `span_id` | null on this record | HIGH | IDENTITY | Spans live on observation events |
| `parent_span_id` | null on this record | HIGH | IDENTITY | Spans live on observation events |
| `session_id` | UTF-8 string, max `OPTICS_SESSION_ID_MAX_BYTES`, or absent | HIGH | IDENTITY | Optional. Rules in section 11. Never a metric label |
| `session_id_basis` | enum in section 11, or absent | LOW | STRUCTURAL | Required when `session_id` is present. Absent when `session_id` is absent |
| `process_id` | integer or null | HIGH | IDENTITY | Null when the runtime does not provide it. Not guessed |
| `parent_process_id` | integer or null | HIGH | IDENTITY | OS parent when provided. Not inferred from timestamps |
| `producer_id` | string, max 80, charset `[A-Za-z0-9_-]` | HIGH | IDENTITY | One producer stream. New at process start. Not equal to `run_id` |
| `producer_sequence` | integer >= 0 | HIGH | IDENTITY | Scoped to `producer_id`. Not a global order |
| `runtime` | enum `node` or `python` | LOW | STRUCTURAL | |
| `runtime_version` | string, max 32 | BOUNDED | STRUCTURAL | |
| `cli_or_sdk_version` | string, max 32 | BOUNDED | STRUCTURAL | |
| `platform` | string, max 32 | LOW | STRUCTURAL | `process.platform` / `sys.platform` values only |
| `arch` | string, max 32 | LOW | STRUCTURAL | |
| `started_at` | UTC RFC3339 | HIGH | STRUCTURAL | |
| `ended_at` | UTC RFC3339 or null | HIGH | STRUCTURAL | |
| `duration_ms` | integer >= 0 or null | BOUNDED | STRUCTURAL | Monotonic measurement. Null if the clock was not usable |
| `clock_quality` | enum `MONOTONIC`, `WALL_CLAMPED`, `UNAVAILABLE` | LOW | DIAGNOSTIC | |
| `lifecycle` | enum `COMPLETE`, `PARTIAL`, `INTERRUPTED`, `ABANDONED`, `RECOVERED` | LOW | STRUCTURAL | |
| `coverage_note` | enum, not free text | LOW | DIAGNOSTIC | For example `WRAPPED_PROCESS`. No hostnames |
| `call_count` | integer >= 0 | BOUNDED | STRUCTURAL | |
| `dropped_count` | integer >= 0 | BOUNDED | STRUCTURAL | Explicit. Zero is allowed |
| `producer` | enum `node_interceptor`, `python_observe`, `demo_command` | LOW | STRUCTURAL | |
| `identity_conflict` | enum `NONE`, `PARENT`, `PRODUCER_SEQUENCE` | LOW | DIAGNOSTIC | `NONE` when no conflict is known |

Not in this record: username, machine hostname, working directory, environment dump, command line, prompts.

### 4.2 Record type `observation_event`

| Field | Type | Cardinality | Privacy | Notes |
| --- | --- | --- | --- | --- |
| `record_type` | const `observation_event` | LOW | STRUCTURAL | |
| `schema_status` | const `unstable-pre-1.0` | LOW | STRUCTURAL | |
| `schema_version` | integer | LOW | STRUCTURAL | |
| `evidence_origin` | origin enum | LOW | STRUCTURAL | |
| `event_id` | string, max 160 | HIGH | IDENTITY | Encoding in A4. Architecture maximum, not a public compatibility claim |
| `run_id` | string | HIGH | IDENTITY | |
| `parent_run_id` | string or null | HIGH | IDENTITY | Same rules as the envelope |
| `trace_id` | string or null | HIGH | IDENTITY | Validated or null |
| `trace_id_basis` | enum in A4, or null | LOW | STRUCTURAL | Required when `trace_id` is present |
| `span_id` | string or null | HIGH | IDENTITY | Max 32 when present. Hex rules in A4 |
| `parent_span_id` | string or null | HIGH | IDENTITY | |
| `session_id` | UTF-8 string or absent | HIGH | IDENTITY | Section 11. Never a metric label |
| `session_id_basis` | enum in section 11, or absent | LOW | STRUCTURAL | Paired with `session_id` |
| `producer_id` | string | HIGH | IDENTITY | Same stream as the envelope |
| `producer_sequence` | integer >= 0 | HIGH | IDENTITY | Identity and tie-break input. Not a global counter |
| `sequence` | integer >= 0 | HIGH | IDENTITY | Equal to `producer_sequence` for this event |
| `destination_host` | hostname or IP literal, max 253 | HIGH | STRUCTURAL | No URL, no userinfo, no query |
| `destination_port` | integer 1–65535 or null | BOUNDED | STRUCTURAL | Null when the default for the scheme was not observed as an explicit port |
| `scheme` | enum `http`, `https`, `ws`, `wss`, `unknown` | LOW | STRUCTURAL | |
| `method` | enum of HTTP methods plus `unknown` | LOW | STRUCTURAL | |
| `path` | string, max 512 | HIGH | STRUCTURAL | Path only. See normalization |
| `provider_id` | catalog id or `unknown` | BOUNDED | STRUCTURAL | No substring guess |
| `provider_confidence` | enum `CATALOG`, `REGIONAL_PATTERN`, `LOCAL_OLLAMA`, `NONE` | LOW | DIAGNOSTIC | |
| `http_status` | integer 100–599 or null | BOUNDED | STRUCTURAL | |
| `application_status` | `SUCCESS`, `APPLICATION_ERROR`, `UNAVAILABLE`, `NOT_OBSERVED` | LOW | STRUCTURAL | From HTTP status rules already in `applicationStatusFromHttp` |
| `optics_status` | vocabulary in `optics-cx.cjs` | LOW | STRUCTURAL | |
| `issue_location` | enum in section 3, including `NONE` | LOW | DIAGNOSTIC | |
| `action` | enum `OBSERVED` for Optics | LOW | STRUCTURAL | Enforcement actions are not Optics evidence |
| `started_at` | UTC RFC3339 | HIGH | STRUCTURAL | |
| `duration_ms` | integer >= 0 or null | BOUNDED | STRUCTURAL | |
| `clock_quality` | same enum as the envelope | LOW | DIAGNOSTIC | |
| `request_bytes` | integer >= 0 or null | BOUNDED | STRUCTURAL | Length only |
| `response_bytes` | integer >= 0 or null | BOUNDED | STRUCTURAL | Length only. Null if unknown. Never invented |
| `content_type` | media type, max 64, no parameters | BOUNDED | STRUCTURAL | |
| `error_class` | token, max 64, `[A-Za-z0-9_]` | BOUNDED | DIAGNOSTIC | Type name only |
| `failure_kind` | enum `dns`, `connection`, `tls`, `timeout`, `network`, `wrapped`, `none` | LOW | DIAGNOSTIC | |
| `mediation` | enum of hooked client names | LOW | STRUCTURAL | For example `node_fetch`, `python_urllib` |
| `duplicate_of` | event id or null | HIGH | IDENTITY | |
| `sampling` | const `UNSAMPLED` until a future policy exists | LOW | STRUCTURAL | |
| `lifecycle` | same lifecycle enum | LOW | STRUCTURAL | |
| `identity_conflict` | enum `NONE`, `PARENT`, `PRODUCER_SEQUENCE` | LOW | DIAGNOSTIC | Visible conflict. Does not drop the row |

### 4.3 Record type `derived_diagnostic`

| Field | Type | Cardinality | Privacy |
| --- | --- | --- | --- |
| `record_type` | const `derived_diagnostic` | LOW | STRUCTURAL |
| `evidence_origin` | const `DERIVED_DIAGNOSTIC` | LOW | STRUCTURAL |
| `schema_status` | const `unstable-pre-1.0` | LOW | STRUCTURAL |
| `subject_event_id` or `subject_run_id` | string | HIGH | IDENTITY |
| `application_outcome_label` | short enum-backed phrase, max 80 | BOUNDED | DIAGNOSTIC |
| `provider_response_phrase` | fixed phrase from the HTTP or failure-kind table, max 80 | BOUNDED | DIAGNOSTIC |
| `next_action_category` | enum `inspection`, `remediation` | LOW | DIAGNOSTIC |
| `issue_location` | enum in section 3, including `NONE` | LOW | DIAGNOSTIC |

Phrases are chosen from a fixed table. They are not copies of exception messages or response bodies.

### 4.4 Record type `annotation`

| Field | Type | Cardinality | Privacy |
| --- | --- | --- | --- |
| `record_type` | const `annotation` | LOW | STRUCTURAL |
| `annotation_role` | const `CUSTOMER_ANNOTATION` | LOW | STRUCTURAL | Required. This record has no observation `evidence_origin`. A seventh origin is not added |
| `annotation_id` | string | HIGH | IDENTITY |
| `subject_run_id` | string | HIGH | IDENTITY |
| `created_at` | UTC RFC3339 | HIGH | STRUCTURAL |
| `text` | string, max 280 | HIGH | CUSTOMER_TEXT |

Annotation text is customer-entered context. It is not scanned as if it were a prompt to store, and it is not written into the observation record. A future implementation must reject annotation text that fails the same secret-shaped checks used on structural fields, rather than store the secret. That check is specified here and not implemented.

Founder note: the origin enum in the Force list does not include a dedicated annotation origin. This pack keeps annotations out of the observation origin enum and uses `annotation_role`. Whether Founders want a seventh origin is unresolved (`NEEDS_FOUNDER_DECISION`), and this pack does not add one silently.

### 4.5 Record type `product_health`

| Field | Type | Cardinality | Privacy |
| --- | --- | --- | --- |
| `record_type` | const `product_health` | LOW | STRUCTURAL |
| `evidence_origin` | const `PRODUCT_HEALTH` | LOW | STRUCTURAL |
| `schema_status` | const `unstable-pre-1.0` | LOW | STRUCTURAL |
| `name` | enum of diagnostic names in A5 | LOW | DIAGNOSTIC |
| `value` | number or short enum | BOUNDED | DIAGNOSTIC |
| `observed_at` | UTC RFC3339 | HIGH | STRUCTURAL |
| `detail_code` | token, max 64 | BOUNDED | DIAGNOSTIC |

No hostnames of customer calls, no event ids in metric labels, no dropped payload.

### 4.6 Record type `proof_manifest`

Defined in A2. It is `manifest.json`, an export beside `proof.json`, not an operational row. The allowlist is the manifest field list in A2. It includes completeness and completeness reasons. It excludes prompts, completions, raw bodies, credentials, and customer payloads.

### 4.7 Record type `import_quarantine`

| Field | Type | Notes |
| --- | --- | --- |
| `record_type` | const `import_quarantine` | |
| `evidence_origin` | const `IMPORTED` | |
| `source_label` | string, max 120 | Caller label, not a raw filesystem path copied from outside the evidence root |
| `content_sha256` | hex | Hash of the imported bytes |
| `schema_status_seen` | string, max 64 | |
| `original_evidence_origin` | allowlisted origin or `LEGACY_UNMARKED` | Preserved from the imported bytes. Not promoted |
| `imported_at` | UTC RFC3339 | Import provenance, separate from the original origin |
| `accepted` | boolean | Default false |
| `reason_code` | token | |

## 5. Prohibited data

If a value is not produced by the allowlist above, it is prohibited. The following are prohibited even if a caller tries to place them in an allowlisted string:

- Prompt text, completion text, message arrays, and request or response bodies.
- Authorization headers, cookies, `Set-Cookie`, API keys, bearer tokens, and any header map.
- URL query strings, URL userinfo, and full URL strings.
- Exception messages, provider error bodies, and stack traces.
- Environment blocks, command lines, local usernames, home-directory paths, and machine hostnames.
- The product-telemetry `anonymousId`.
- Payment, health, or government-identifier patterns that match the existing PII categories (SSN, email, credit card, phone) when they appear inside `path`, `destination_host`, `error_class`, annotation text, or any other persisted string.
- Encoded lookalikes of those secrets (percent-encoding, base64 of a token shape, Unicode confusables of `sk-` style tokens) inside those strings. The privacy corpus defines the fixtures. This pack does not implement the corpus.
- Baggage or trace-state values that are not on the trace-id allowlist. Opaque baggage is dropped, not stored.

`path` longer than 512 characters is rejected, not truncated into storage, so a secret is not kept as a prefix.

Recovery when a prohibited value is detected: omit the field or drop the event, increment product-health `redaction_failure`, and continue the application. Do not store a reversible mask of the secret.

## 6. Privacy failure behavior

These are release-blocking invariants for any future implementation Force. They are not claimed to pass today.

1. A persisted observation, envelope, proof, diagnostic, quarantine row, or telemetry body contains only allowlisted keys.
2. Fixtures that place tokens in headers, query strings, paths, exception messages, and nested or encoded fields do not appear in the persisted record or the proof bytes.
3. Demo, fixture, imported, product-health, derived, and `LEGACY_UNMARKED` records do not appear in operational trend totals.
4. Product telemetry bytes are not written under the evidence store, and evidence bytes are not posted to the telemetry URL.
5. A privacy-weaker schema cannot be opened as a writer over a store that already used a stronger allowlist.
6. Failure of invariant 1 or 2 blocks release. The application under observation still receives its own response. Optics must not invent a successful observation to hide the failure.

Current source does not implement this suite. Topic 17 of the inventory is `PARTIAL`. That is not a pass.

## 7. Product telemetry separation

Optional Vantio product telemetry stays on the channel already implemented in `telemetry.cjs` and `_telemetry.py`.

- Default off.
- Disable precedence: `VANTIO_TELEMETRY_DISABLED=1` and `DO_NOT_TRACK=1` override `VANTIO_TELEMETRY=1`.
- Destination: `{base}/api/v1/telemetry`, base from `VANTIO_INGEST_URL` or `https://vantio.ai`, HTTP(S) only.
- Fields: the allowlist already enforced by those modules. No expansion in this architecture.
- Trigger: at most one `run` event per process, plus a `summary` event only if a future caller already has that behavior. This pack does not add a new trigger.
- Frequency: once per process for the `run` event. No retry storm.
- Last result: not stored today. A future product-health field `telemetry_last_result` with enum `DISABLED`, `SENT`, `FAILED`, `SKIPPED` is allowed. It must not include the response body.
- The anonymous id file stays `~/.vantio/telemetry-id` and is not an observation.

Customer evidence and this ping are different products of the same install. A proof artifact must not embed the anonymous id.

## 8. Optics and enforcement

Optics observation evidence uses `action: OBSERVED` only. Block, redact, and spend-cap actions belong to Phantom Engine enforcement and are outside this contract. A future Optics writer must not persist enforcement actions as if they were Optics observations. Co-located enforcement code may continue to exist until a separate product change; this pack does not redesign it and does not authorize that change.

## 9. Unresolved Founder decisions inside this contract

- Whether customer annotations need their own origin enum value. This pack uses `annotation_role` and does not add an origin.
- Whether an explicit customer promote may stamp `LEGACY_UNMARKED` as `LOCAL_OBSERVATION`. Preservation of an allowlisted origin that already has recognized provenance is specified above and is not that promote decision.
- Usage and cost metadata from provider responses. Not in the allowlist. Roadmap item OF-05 stays `NEEDS_FOUNDER_DECISION`.

## 10. Non-executable illustration

The following is a shape check, not a parser.

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```json
{
  "record_type": "observation_event",
  "schema_status": "unstable-pre-1.0",
  "schema_version": 0,
  "evidence_origin": "LOCAL_OBSERVATION",
  "event_id": "evt_example",
  "run_id": "run_example",
  "destination_host": "api.openai.com",
  "provider_id": "openai",
  "provider_confidence": "CATALOG",
  "http_status": 200,
  "application_status": "SUCCESS",
  "optics_status": "SUCCESS",
  "issue_location": "NONE",
  "action": "OBSERVED",
  "sampling": "UNSAMPLED",
  "lifecycle": "COMPLETE"
}
```

`optics_status` `SUCCESS` in the example means the record was stored. HTTP 200 has issue location `NONE`.

An observed HTTP 401 on a stored event uses `application_status` `APPLICATION_ERROR`, `issue_location` `PROVIDER_INTERACTION`, and human label “Provider interaction.”

`schema_version` 0 in the example means “not yet assigned by an implementation Force.” It is not a stable schema.

## 11. `session_id`

`session_id` is optional. It groups runs when an explicit source sets it. It is not inferred from time, trace id, process id, or hostname.

Architecture constant `OPTICS_SESSION_ID_MAX_BYTES` is 80. The constant counts UTF-8 bytes. It is an unstable pre-1.0 architecture limit, not a public compatibility claim.

`session_id_basis` is required on the same record when `session_id` is present, and absent when `session_id` is absent. Values:

- `OPTICS_GENERATED` — Optics minted the id. An application payload cannot select this basis.
- `APPLICATION_SUPPLIED` — an explicit application API supplied the id.
- `CUSTOMER_SUPPLIED` — an explicit customer input supplied the id.
- `IMPORTED_UNVERIFIED` — the id arrived by import and stronger provenance is absent.
- `LEGACY_UNMARKED` — a legacy file carried a value that passed the checks below and recorded no basis.

Encoding and acceptance:

- Well-formed UTF-8.
- Unicode Normalization Form C. A value that is not NFC is rejected. The writer does not rewrite it.
- No code point U+0000 through U+001F, and no U+007F.
- No Unicode noncharacter (U+FDD0 through U+FDEF, or any code point whose scalar ends in FFFE or FFFF).
- No leading or trailing U+0020. The writer does not trim.
- No case folding, compatibility folding, or path normalization.
- Byte length at most `OPTICS_SESSION_ID_MAX_BYTES`. Overlong values are rejected whole. They are not truncated.
- The prohibited-data checks in section 5 apply. The value is also rejected when it contains `/`, `\`, or `@`.
- Email addresses, credentials, prompts, filesystem paths, and secrets are not accepted as session ids.

Invalid value, missing basis, or a basis outside the enum: omit both fields, increment product-health `session_id_rejected`, and continue the application. Do not store the rejected bytes.

Collision: `session_id` is not a unique key. Two runs may share one id. Sharing does not merge `run_id`, `trace_id`, `process_id`, `producer_id`, or `event_id`.

Cardinality is `HIGH`. A future metric must not use `session_id` as a label.

Query: equality on the stored UTF-8 bytes only. No prefix, substring, or caller regular expression. The response includes `session_id_basis`.

Proof: when a proof includes the field, it includes `session_id_basis` on the same object. The proof profile in A2 applies. The field is not a metric label inside the proof.

Import: default basis is `IMPORTED_UNVERIFIED`. A recorded basis from the imported bytes is preserved only when the import also meets the recognized-producer provenance rule in section 2, and that preservation does not change `IMPORTED_UNVERIFIED` or `LEGACY_UNMARKED` into `OPTICS_GENERATED`.

### 11.1 Architecture test plan — `session_id`

Specified, not executed. No evidence tier is assigned.

- A well-formed NFC value within 80 bytes, with a legal basis, is stored with that basis.
- Invalid UTF-8, non-NFC text, a control character, a leading space, a value over 80 bytes, a value containing `/` or `@`, and a secret-shaped value are omitted rather than truncated.
- `session_id` without `session_id_basis`, or a basis without `session_id`, stores neither field.
- An imported id without stronger provenance is stored as `IMPORTED_UNVERIFIED`.
- A metric-label fixture that uses `session_id` is rejected by the cardinality rule.
