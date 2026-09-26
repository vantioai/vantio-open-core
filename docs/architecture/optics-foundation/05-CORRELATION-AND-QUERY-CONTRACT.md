# A4 — Correlation and bounded query

Classification: `OPTICS_FOUNDATION_A4_CONTRACT_READY`

Audience: INTERNAL_RESTRICTED

## 1. Identity hierarchy

From broader to narrower:

1. Evidence root (the directory). Not a customer identifier and not a metric label.
2. `run_id` — one attached process execution of Optics. This is what today’s `trace_id` actually is.
3. `session_id` — optional group of runs. Absent unless set by an explicit future API or a validated incoming value. It is not inferred from time proximity.
4. `trace_id` — optional application or W3C trace id after validation.
5. `span_id` and `parent_span_id` — optional, validated, not guessed from order.
6. `event_id` — one observation attempt.
7. `sequence` — integer assigned by the writer inside the run, starting at 0.

`process_id` and `parent_process_id` sit beside the run. They are not parents of `trace_id`.

Today’s file name is the trace id. After migration, the file name of a legacy object may still be that string, and the mapped `run_id` is that string. New writes mint `run_id` and do not overload it as `trace_id`.

## 2. Correlation rules

- A call correlates to a run because the writer stamped `run_id` while the hook was installed. It does not correlate because two timestamps are close.
- Child processes inherit correlation only when they inherit the instrumentation and the id environment (`VANTIO_TRACE_ID` today). If they do not, they are a coverage gap, not a child span.
- Async and threads share `run_id` when they share the process install. Python already locks the in-memory list. The store writer must keep `sequence` monotonic per `run_id`.
- A retry is a new `event_id` with the same `run_id`. It may set `duplicate_of` only when the writer knows it is the same logical attempt. Otherwise it is a separate event. Counts do not collapse retries unless the query asks for deduplicated counts.
- Incoming trace context that is malformed, oversized (over 128 characters for a trace id, over 32 for a span id), or not hexadecimal (W3C) or not in the legacy `0x` plus hex form, is dropped. The event is still stored with null trace fields and a product-health `rejected_context` count. The bad context is not stored.
- Sensitive baggage is not on the allowlist. It is dropped.
- Collision: if two accepted contexts disagree inside one call, store neither as parent, set issue location `CONFIGURATION` on the diagnostic, and keep the local `run_id`.

No causal claim is made from timestamp order. Ordering for display is `started_at`, then `sequence`, then `event_id`.

## 3. Deduplication

`event_id` is a writer-generated id, unique inside a store. The canonical input is the tuple (`producer`, `run_id`, `sequence`). The id is that tuple’s stable encoding, not a hash of the body.

- A second insert with the same `event_id` is a duplicate. The store keeps one observation and may set `duplicate_of` on a product-health note. Metrics use the deduplicated set.
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
| `run_id`, `session_id`, `trace_id`, `process_id` | Exact match |
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
| `sort` | `started_at_asc` or `started_at_desc` only |

Rejected:

- Arbitrary SQL, including from a local UI text box.
- Caller regular expressions. They are a denial-of-service risk and are not required for the filters above.
- Paths outside the evidence root.
- A filter that requires reading a body.

Saved views store this request object, not a copy of the events.

### 5.2 Response fields

- `schema_status`
- `completeness` of the answer: `COMPLETE`, `PARTIAL`, `TRUNCATED_BY_LIMIT`, `UNAVAILABLE`
- `freshness`
- `origin_filter`
- `scanned_bounded`: true when the engine used indexes on allowlisted fields
- `rows`: allowlisted view
- `next_cursor` or null
- `limitation` string from a fixed table, not from stored customer text

A truncated result is not displayed as a complete population.

### 5.3 Cost

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
| Demo rows included in every scan | Excluded unless `origin` includes `SIMULATED_DEMO` |

## 8. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```json
{
  "schema_status": "unstable-pre-1.0",
  "time_start": "2026-09-01T00:00:00Z",
  "time_end": "2026-09-26T00:00:00Z",
  "provider_id": "openai",
  "origin": "LOCAL_OBSERVATION",
  "limit": 100,
  "sort": "started_at_desc"
}
```
