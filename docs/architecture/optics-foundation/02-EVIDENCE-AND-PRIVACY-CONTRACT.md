# A1 — Evidence and privacy contract

Classification: `OPTICS_FOUNDATION_A1_CONTRACT_READY`

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
- `LEGACY_UNMARKED` is excluded from operational trends and from any future baseline, the same way demo and fixture evidence are excluded.
- A legacy file whose destination is `optics-demo.invalid` is `SIMULATED_DEMO` on read. It is not promoted to `LOCAL_OBSERVATION`.
- Import never writes `LOCAL_OBSERVATION`.
- Product telemetry is not given an evidence origin inside the operational store because it is not stored there.
- Derived fields that today sit inside the Python call object (`applicationOutcomeLabel`, `nextAction`, and the summary human lines) are `DERIVED_DIAGNOSTIC` in this contract. A future writer may keep a copy beside the observation. It must not be required in order to trust the observation.

## 3. Issue location

Machine values, stored on diagnostics and on command results when a failure is classified:

- `OPTICS`
- `CUSTOMER_APPLICATION`
- `PROVIDER_INTERACTION`
- `NETWORK`
- `ENVIRONMENT`
- `CONFIGURATION`
- `COVERAGE`
- `UNKNOWN`

Human text uses “issue location” or “failing interaction layer.” It does not assign legal blame, negligence, or ownership of a vendor relationship.

Mapping from current behavior, for the future writer:

| Current signal | Issue location |
| --- | --- |
| Run-log write, parse, migration, or redaction failure | `OPTICS` |
| HTTP status 400–599 on an observed call | `PROVIDER_INTERACTION` when provider identity is catalog-confident; otherwise `CUSTOMER_APPLICATION` is wrong for a provider 4xx. Use `PROVIDER_INTERACTION` only with catalog confidence, else `UNKNOWN` for the provider layer and keep the HTTP code |
| Python `failure_kind` dns, connection, tls, timeout, network | `NETWORK` |
| Process not wrapped, or client not in the hooked set | `COVERAGE` |
| `VANTIO_HOME` reader/writer split, bad config | `CONFIGURATION` |
| Exception class `wrapped` with no HTTP status | `CUSTOMER_APPLICATION` |
| Anything else | `UNKNOWN` |

The HTTP code remains the application outcome. Issue location does not replace `applicationStatus`.

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
| `run_id` | string, max 80, charset `[A-Za-z0-9_-]` | HIGH | IDENTITY | New. Not the per-call span |
| `trace_id` | string, max 80 | HIGH | IDENTITY | Optional W3C-shaped id when the application supplied one that passed validation. Not a synonym for `run_id` |
| `session_id` | string, max 80 | HIGH | IDENTITY | Optional. Absent until the application or a future explicit API sets it |
| `process_id` | integer | HIGH | IDENTITY | |
| `parent_process_id` | integer or null | HIGH | IDENTITY | |
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

Not in this record: username, machine hostname, working directory, environment dump, command line, prompts.

### 4.2 Record type `observation_event`

| Field | Type | Cardinality | Privacy | Notes |
| --- | --- | --- | --- | --- |
| `record_type` | const `observation_event` | LOW | STRUCTURAL | |
| `schema_status` | const `unstable-pre-1.0` | LOW | STRUCTURAL | |
| `schema_version` | integer | LOW | STRUCTURAL | |
| `evidence_origin` | origin enum | LOW | STRUCTURAL | |
| `event_id` | string, max 80 | HIGH | IDENTITY | Stable for deduplication |
| `run_id` | string | HIGH | IDENTITY | |
| `trace_id` | string or null | HIGH | IDENTITY | Validated or null |
| `span_id` | string or null | HIGH | IDENTITY | |
| `parent_span_id` | string or null | HIGH | IDENTITY | |
| `session_id` | string or null | HIGH | IDENTITY | |
| `sequence` | integer >= 0 | HIGH | IDENTITY | Per run. Tie-break |
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
| `issue_location` | fault-domain enum | LOW | DIAGNOSTIC | |
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
| `issue_location` | fault-domain enum | LOW | DIAGNOSTIC |

Phrases are chosen from a fixed table. They are not copies of exception messages or response bodies.

### 4.4 Record type `annotation`

| Field | Type | Cardinality | Privacy |
| --- | --- | --- | --- |
| `record_type` | const `annotation` | LOW | STRUCTURAL |
| `evidence_origin` | const `DERIVED_DIAGNOSTIC` is wrong for this row. Origin is not an observation origin. Use a required `annotation_role` = `CUSTOMER_ANNOTATION` and do not set an observation origin | LOW | STRUCTURAL |
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

Defined in A2. It is an export, not the operational row. Fields are an allowlist: schema identity, origin counts, time range, event-id list or hash rollup, redaction posture `ALLOWLIST_ONLY`, completeness, sampling `UNSAMPLED`, producer versions, and the hash of the canonical proof bytes. No secrets.

### 4.7 Record type `import_quarantine`

| Field | Type | Notes |
| --- | --- | --- |
| `record_type` | const `import_quarantine` | |
| `evidence_origin` | const `IMPORTED` | |
| `source_label` | string, max 120 | Caller label, not a raw filesystem path copied from outside the evidence root |
| `content_sha256` | hex | Hash of the imported bytes |
| `schema_status_seen` | string, max 64 | |
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
3. Demo, fixture, imported, product-health, and derived records do not appear in operational trend totals.
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
- Whether a legacy file other than the demo host may ever be stamped `LOCAL_OBSERVATION`, and only under an explicit migration the customer runs. Default here: no automatic stamp.
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
  "issue_location": "PROVIDER_INTERACTION",
  "action": "OBSERVED",
  "sampling": "UNSAMPLED",
  "lifecycle": "COMPLETE"
}
```

`schema_version` 0 in the example means “not yet assigned by an implementation Force.” It is not a stable schema.
