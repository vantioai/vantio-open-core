# A4 — Correlation and bounded query

Classification: `OPTICS_FOUNDATION_A4_CONTRACT_READY`

Revision: `OPTICS_FOUNDATION_ARCHITECTURE_REVISION_READY_FOR_RECOUNCIL`. Gate 5 stays reopened until a fresh council passes. This line is not a council pass.

Audience: INTERNAL_RESTRICTED

## 1. Identity hierarchy

From broader to narrower:

1. Evidence root (the directory). Not a customer identifier and not a metric label.
2. `session_id` — optional group of runs, including a parent and a child. Rules in A1 section 11. It is not inferred from time proximity.
3. `run_id` — one wrapped execution boundary. This is what today’s `trace_id` actually is. A child process that is independently wrapped or attached receives a new `run_id`.
4. `trace_id` — optional trace context after validation. Propagation is context only.
5. `span_id` and `parent_span_id` — optional, validated, not guessed from order.
6. `event_id` — one observation attempt.

Required identity fields on the run envelope and on each observation event: `process_id`, `parent_process_id`, `run_id`, `parent_run_id`, `trace_id`, `trace_id_basis`, `span_id`, `parent_span_id`, `producer_id`, `producer_sequence`. A field that was not observed is null, and the null is stored. It is not filled by guessing. `span_id` and `parent_span_id` are null on the run envelope.

`trace_id_basis` values: `OPTICS_GENERATED`, `APPLICATION_SUPPLIED`, `ASSERTED_CONTEXT`, `IMPORTED_UNVERIFIED`, `LEGACY_UNMARKED`, `UNKNOWN`. The basis is present only when `trace_id` is present.

`VANTIO_TRACE_ID`, when it matches the trace-id syntax below, is copied to `trace_id` with basis `ASSERTED_CONTEXT`. That value is asserted context. It is not observation proof, it does not mint `run_id`, and it does not make an unobserved child `LOCAL_OBSERVATION`.

`VANTIO_PARENT_RUN_ID`, when it matches the `run_id` charset, is copied to `parent_run_id`. If it is absent or invalid, `parent_run_id` is null. Parenthood is that explicit value together with `parent_process_id` from the operating system when the runtime provides it. Shared `trace_id`, shared `session_id`, and close timestamps do not set `parent_run_id`.

`producer_id` is minted at process start, charset `[A-Za-z0-9_-]`, max 80, and is not equal to `run_id`. A restart mints a new `producer_id`. `producer_sequence` starts at 0 for that stream and increases by 1 for each accepted observation. It is not a global order. `sequence` on an event equals that event’s `producer_sequence`.

Global display order is canonical `started_at`, then `producer_id` in UTF-8 byte order, then `producer_sequence`, then `event_id` in UTF-8 byte order.

`event_id` is the stable encoding `e.` + decimal byte length of `producer_id` + `.` + `producer_id` + `.` + decimal `producer_sequence`. Example: producer `p1`, sequence `0`, yields `e.2.p1.0`. Two processes cannot mint the same `event_id` unless they reuse one `producer_id`.

Today’s file name is the trace id. After migration, the file name of a legacy object may still be that string, and the mapped `run_id` is that string. New writes mint `run_id` and do not overload it as `trace_id`.

Child rules:

- A session may group a parent run and a child run. Grouping does not merge the runs.
- An observed child has its own `process_id`, `producer_id`, and `producer_sequence`.
- A detached, unsupported, or unobserved child does not get a synthetic `LOCAL_OBSERVATION` row. The parent records the gap. Issue location is `COVERAGE` when the gap is evidenced, otherwise `UNKNOWN`. Application status for the missing call is `NOT_OBSERVED`. Run lifecycle may be `PARTIAL`.
- Inherited trace context is not `LOCAL_OBSERVATION`.
- Conflicting parenthood keeps both observed values and sets `identity_conflict` to `PARENT`. The writer does not pick a winner from timestamps.
- A repeated `(producer_id, producer_sequence)` with the same allowlisted identity fields is an idempotent duplicate and is counted. A repeat with different `run_id`, `trace_id`, or destination keeps both rows and sets `identity_conflict` to `PRODUCER_SEQUENCE`. Neither row is discarded.
- Malformed trace context is dropped. `trace_id` stays null. The bad context is not stored.
- Replayed trace context with a new `producer_id` is a new observation. Basis stays `ASSERTED_CONTEXT` or `IMPORTED_UNVERIFIED` as the source requires. It does not become the original run.
- Several children with one `trace_id` stay distinguishable by `run_id`, `process_id`, `producer_id`, and `span_id`.

### 1.1 Architecture test plan — child process

Specified, not executed. No evidence tier is assigned.

| Case | Required outcome |
| --- | --- |
| Parent plus a wrapped child | Child has a new `run_id`, its own `process_id` and `producer_id`, and `parent_run_id` only when `VANTIO_PARENT_RUN_ID` was valid |
| Parent plus a detached child | No synthetic child observation. Parent gap is `PARTIAL`, `NOT_OBSERVED`, and `COVERAGE` or `UNKNOWN` |
| Two children, one `trace_id` | Distinct `run_id`, `process_id`, `producer_id`, and `span_id` |
| Process restart | New `process_id`, new `producer_id`, `producer_sequence` restarts at 0, new `run_id` |
| Inherited trace without an observed child | `ASSERTED_CONTEXT` on the parent. No child `LOCAL_OBSERVATION` |
| Conflicting parent | Both claims remain. `identity_conflict` is `PARENT` |
| Duplicate producer sequence with a different identity | Both rows remain. `identity_conflict` is `PRODUCER_SEQUENCE` |
| Cross-process timestamp tie | Order uses the global tie-breakers. The tie does not assign parenthood |
| Malformed trace | Trace fields null. Context not stored |
| Replayed context | New observation under the new producer stream. Not proof of the original run |

## 2. Correlation rules

- A call correlates to a run because the writer stamped `run_id` while the hook was installed. It does not correlate because two timestamps are close.
- Child processes receive a new `run_id` when they are independently wrapped or attached. `VANTIO_TRACE_ID` propagates trace context only, with basis `ASSERTED_CONTEXT`. A child that does not inherit instrumentation is a coverage gap, not a child span, and not `LOCAL_OBSERVATION`.
- Async and threads share `run_id` when they share the process install. Python already locks the in-memory list. `producer_sequence` stays monotonic for one `producer_id`.
- A retry is a new `event_id` with the same `run_id` and the next `producer_sequence`. It may set `duplicate_of` only when the writer knows it is the same logical attempt. Otherwise it is a separate event. Counts do not collapse retries unless the query asks for deduplicated counts.
- Incoming trace context that is malformed, oversized (over 128 characters for a trace id, over 32 for a span id), or not hexadecimal (W3C) or not in the legacy `0x` plus hex form, is dropped. The event is still stored with null trace fields and a product-health `rejected_context` count. The bad context is not stored.
- Sensitive baggage is not on the allowlist. It is dropped.
- Collision: if two accepted contexts disagree inside one call, store neither as parent, set issue location `CONFIGURATION` on the diagnostic, and keep the local `run_id`.

No causal claim is made from timestamp order. Ordering for display is the global order in section 1.

## 3. Deduplication

`event_id` is a writer-generated id. The canonical input is (`producer_id`, `producer_sequence`), encoded as section 1 specifies. It is not a hash of the body. The producer enum alone is not the namespace.

- A second insert with the same `event_id` and the same allowlisted identity fields is an idempotent duplicate. The store keeps one observation, counts it, and may set `duplicate_of` on a product-health note. Metrics use the deduplicated set. A second insert with the same `event_id` encoding inputs and different identity fields is the `PRODUCER_SEQUENCE` conflict in section 1. Both rows stay visible.
- Multi-hook detection: if two mediations in one process report the same destination, start time within the same sequence slot, and the same byte length, the second is marked duplicate. The numeric time window is `NOT_SET`. Until it is set, only an explicit same-`sequence` collision counts. Do not invent a millisecond window.
- Import of an event id that already exists does not create a second logical event and does not upgrade origin to `LOCAL_OBSERVATION`.
- Demo and fixture rows are ignored by deduplicated operational counts.

Current Node code uses `AsyncLocalStorage` to avoid a second gate event for the same HTTP call. That is an in-process guard, not a durable `event_id`. Inventory: `PARTIAL`.

## 4. Destination and provider identity

These are different fields.

- **Destination** is `destination_host` plus optional `destination_port` plus `scheme` and `path`. It is what was contacted.
- **Provider** is `provider_id` plus `provider_confidence`. It is a catalog label.

Normalization:

- Compare hosts in lowercase ASCII. Store the lowercase form for DNS names. Store IP literals as parsed (IPv6 without brackets in the host field; brackets are not part of the host).
- Do not attach default ports into the stored port field unless the URL contained an explicit port. Scope checks may still assume 443 or 80.
- Strip query, fragment, and userinfo before any persistence. If stripping fails, drop the destination fields and count a redaction failure rather than store the raw URL.
- Redirects are new events if a hooked client makes another request. The first event is not rewritten to the final host.
- Proxies: the observed peer is the destination that the hooked client connected to. Proxy versus origin is not inferred.
- Regional hosts use the existing regional patterns (Bedrock, Vertex, Hugging Face endpoints) and `provider_confidence: REGIONAL_PATTERN`.
- Substring matching, as in `guessProvider`, is not the target algorithm.

Provider confidence:

- `CATALOG` — exact host or DNS suffix of a catalog host.
- `REGIONAL_PATTERN` — the regional patterns already in source.
- `LOCAL_OLLAMA` — localhost, `127.0.0.1`, or `::1` on port 11434.
- `NONE` — `provider_id` is `unknown`. Do not display a vendor name.

No model name is stored unless it appears as its own allowlisted field later. It does not. Model strings often sit in bodies. OF-05 would be required before any usage or model field, and that decision is open.

## 5. Bounded query

One query model for a future CLI, a future local UI, and structured output. This Force does not add a command and does not expose SQL.

### 5.1 Request fields

All optional except `limit`.

| Field | Constraint |
| --- | --- |
| `time_start`, `time_end` | UTC inclusive bounds. Required for any query that is not a single `run_id` lookup |
| `run_id`, `session_id`, `trace_id`, `process_id` | Exact match. `session_id` is exact UTF-8 bytes and returns `session_id_basis` |
| `provider_id` | Exact catalog id or `unknown` |
| `destination_host` | Exact normalized host. No substring in the target contract. Today’s `includes` match is legacy behavior and is not the contract |
| `application_status`, `optics_status`, `issue_location` | Exact enum |
| `http_status` | Integer |
| `duration_min_ms`, `duration_max_ms` | Integers >= 0 |
| `lifecycle` | Exact enum |
| `coverage` | Exact enum |
| `origin` | Exact origin. Default set is `LOCAL_OBSERVATION` only |
| `freshness` | Enum `CURRENT`, `HISTORICAL`, `STALE`, `UNKNOWN`. Definitions in A5 |
| `limit` | Integer 1–500. Default 100. Maximum 500 |
| `cursor` | Opaque continuation from the previous response |
| `sort` | `started_at_asc` or `started_at_desc` only. Equal timestamps then use `producer_id`, `producer_sequence`, and `event_id` |

Rejected:

- Arbitrary SQL, including from a local UI text box.
- Caller regular expressions. They are a denial-of-service risk and are not required for the filters above.
- Paths outside the evidence root.
- A filter that requires reading a body.

Saved views store this request object, not a copy of the events.

### 5.2 Response envelope

Every answer, including a default `LOCAL_OBSERVATION` answer, carries this envelope. Product-health rows stay out of `rows`. Their effect on capture is still on the envelope.

Required fields:

| Field | Meaning |
| --- | --- |
| `declaredScope` | The scope that was asked. Includes time range, filters, origins included, and origins excluded |
| `matchingRecords` | Count of matching records in the evaluated scope, or null when unknown |
| `returnedRecords` | Count of records in this page |
| `hasMore` | Whether another page exists |
| `completeness` | `COMPLETE`, `PARTIAL`, `UNKNOWN`, or `UNAVAILABLE` |
| `completenessReasons` | Tokens. Empty only when completeness is `COMPLETE` |
| `integrityState` | `OK`, `FAILED`, or `UNKNOWN`. From the external recovery envelope when the store is not healthy |
| `samplingState` | `UNSAMPLED`, `SAMPLED`, or `UNKNOWN` |
| `dropState` | `NO_DROPS`, `DROPS_IN_SCOPE`, or `UNKNOWN` |
| `freshness` | Independent of completeness. Values in A5 |
| `schema_status` | `unstable-pre-1.0` |
| `rows` | Allowlisted view for this page |
| `next_cursor` | Opaque cursor, or null |
| `limitation` | Fixed-table phrase, not stored customer text |

Pagination is `hasMore`, `matchingRecords`, `returnedRecords`, and `next_cursor`. Those fields are not completeness.

Completeness describes the declared evidence scope.

- `COMPLETE`: the declared scope was fully evaluated; `integrityState` is `OK`; store health is known; `samplingState` is `UNSAMPLED`; `dropState` is `NO_DROPS`; no required evidence in the scope is corrupt; every run in the scope has lifecycle `COMPLETE`; no coverage gap, parent conflict, or producer-sequence conflict is inside the scope; `matchingRecords` is an integer. A later page of that same evaluated scope may also be `COMPLETE`.
- `PARTIAL`: the scope is known, an answer was produced, and at least one reason below applies. `PARTIAL` is the full word for an evaluated scope that is missing evidence, not a synonym for a full page and not a synonym for `hasMore`. A page that returns every stored row is still `PARTIAL` when a reason applies. Known drops in the scope are `PARTIAL`. Corrupt required evidence that still yields a bounded salvage is `PARTIAL` when some rows are returned, and `UNAVAILABLE` when no trustworthy row can be returned. Salvage is never `COMPLETE`.
- `UNKNOWN`: the evaluator cannot tell whether the declared scope was fully captured. Unknown store health prevents `COMPLETE`. If health is unknown and no positive gap is known, completeness is `UNKNOWN`. If a known drop or other positive gap exists, completeness is `PARTIAL` and the reasons include both the gap and `STORE_HEALTH_UNKNOWN`.
- `UNAVAILABLE`: required evidence cannot be read, including `STOPPED_PRESERVED` before salvage, a refused store, or a salvage that cannot trust its rows. Rows are not presented as a population.

Reason tokens: `DROPS_IN_SCOPE`, `RUN_LIFECYCLE_NOT_COMPLETE`, `SAMPLING_NOT_UNSAMPLED`, `REQUIRED_EVIDENCE_CORRUPT`, `STORE_HEALTH_UNKNOWN`, `INTEGRITY_NOT_OK`, `COVERAGE_GAP_IN_SCOPE`, `EVALUATION_INCOMPLETE`, `REQUIRED_EVIDENCE_UNAVAILABLE`, `PARENT_CONFLICT`, `PRODUCER_SEQUENCE_CONFLICT`.

An untruncated page (`hasMore` false and `returnedRecords` equal to `matchingRecords`) is not automatically `COMPLETE`. A paginated result stays `COMPLETE` when the full declared scope was evaluated and no reason applies. Stopping before the declared scope is evaluated is `EVALUATION_INCOMPLETE`, which is `PARTIAL`, not a complete page.

Filters and the time range are inside `declaredScope`. Default scope includes origin `LOCAL_OBSERVATION` only and lists `LEGACY_UNMARKED`, demo, fixture, imported, product-health, and derived origins as excluded. That exclusion is scope. It is not a hidden hole, and it is not a promotion of legacy evidence.

A trend or rollup carries the source envelope’s `completeness` and `completenessReasons`. It does not upgrade them.

A portable proof copies that completeness and those reasons into `proof.json` and `manifest.json`.

A future UI reads this envelope. It must not present `PARTIAL`, `UNKNOWN`, or `UNAVAILABLE` as a complete or green success state. It uses the A1 human labels for issue location and does not display “Provider fault.” Product-health rows stay off the customer timeline. This Force does not build the UI. The local UI charter remains Founder decision 13.

`scanned_bounded` remains true when the engine used indexes on allowlisted fields.

### 5.3 Architecture test plan — completeness

Specified, not executed. No evidence tier is assigned.

- A page with `hasMore` false and a non-zero drop in scope is `PARTIAL` with `DROPS_IN_SCOPE`.
- A fully evaluated scope with `hasMore` true, `dropState` `NO_DROPS`, `integrityState` `OK`, and `samplingState` `UNSAMPLED` may be `COMPLETE`.
- Unknown `integrityState` is not `COMPLETE`.
- Salvage of corrupt required evidence is `PARTIAL` or `UNAVAILABLE`, never `COMPLETE`.
- `declaredScope` contains the time range and the origin filter.
- A trend fixture repeats the source completeness.
- A proof fixture contains the same completeness and reasons.

### 5.4 Cost

Query-cost limits exist as a requirement. The numeric budget is `NOT_SET` (`NFR-QUERY-LATENCY` and the query-cost bullet). Until a number is set, the structural caps are the limit of 500 rows, a required time range except for a single-run lookup, and no regex. A query that cannot use an allowlisted index is refused, not scanned without bound.

## 6. Cardinality

Indexed fields (the only fields a query may use as a predicate): `started_at`, `run_id`, `session_id`, `trace_id`, `process_id`, `provider_id`, `destination_host`, `application_status`, `optics_status`, `issue_location`, `http_status`, `lifecycle`, `evidence_origin`, `event_id`.

Metric labels, when any future indicator exists, may use only `LOW` cardinality fields from A1: status enums, `provider_id`, `scheme`, `issue_location`, `runtime`, `lifecycle`, `evidence_origin`. They must not use `run_id`, `trace_id`, `session_id`, `event_id`, `path`, or raw `destination_host`.

Host-level counts stay in events and in query results, not in metric labels. A future rollup by provider is allowed. A rollup by full URL is not.

Overflow: when a future queue or cardinality guard drops work, it writes one product-health drop record with a count. It does not write one customer event per drop, and it does not include the dropped payload.

## 7. Current code versus this contract

| Behavior now | Contract |
| --- | --- |
| One `trace_id` per process | Becomes `run_id`. Trace id becomes optional and validated |
| Search substring across all files | Bounded exact filters and a limit |
| Diff of two host rollups | A query, not a second schema |
| Discover cutoff uses file mtime; search uses `generated_at` | One clock: `started_at` / `ended_at` in UTC |
| Demo rows included in every scan | Excluded unless `origin` includes `SIMULATED_DEMO`. `LEGACY_UNMARKED` stays out of the default trend scope |

## 8. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```json
{
  "schema_status": "unstable-pre-1.0",
  "declaredScope": {
    "time_start": "2026-09-01T00:00:00.000Z",
    "time_end": "2026-09-26T00:00:00.000Z",
    "origins_included": ["LOCAL_OBSERVATION"],
    "origins_excluded": ["LEGACY_UNMARKED", "SIMULATED_DEMO", "TEST_FIXTURE", "IMPORTED", "PRODUCT_HEALTH", "DERIVED_DIAGNOSTIC"]
  },
  "matchingRecords": 2,
  "returnedRecords": 1,
  "hasMore": true,
  "completeness": "PARTIAL",
  "completenessReasons": ["DROPS_IN_SCOPE"],
  "integrityState": "OK",
  "samplingState": "UNSAMPLED",
  "dropState": "DROPS_IN_SCOPE",
  "freshness": "UNKNOWN"
}
```

`hasMore` true does not set completeness. `DROPS_IN_SCOPE` keeps this answer `PARTIAL` even if the returned page is internally consistent.
