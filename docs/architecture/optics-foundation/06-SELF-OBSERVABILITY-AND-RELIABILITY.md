# A5 — Self-observability, performance, and fail-open

Classification: `OPTICS_FOUNDATION_A5_CONTRACT_READY`

Audience: INTERNAL_RESTRICTED

No numeric performance target is adopted. Every budget’s current target is `NOT_SET`. The roadmap example “<5ms p99” is an example in that document and is not a target of this pack.

## 1. Self-observability

Optics records its own health as `PRODUCT_HEALTH` records. Those records are not customer AI calls, not provider calls, and not rows returned by the default observation query.

Diagnostic names (the `name` enum):

- `hooks_installed`
- `events_received`
- `events_persisted`
- `events_rejected`
- `events_dropped`
- `write_latency_ms` (measurement method `NOT_SET`)
- `query_latency_ms` (measurement method `NOT_SET`)
- `database_size_bytes`
- `last_successful_write_at`
- `integrity_state` (`OK`, `FAILED`, `UNKNOWN`)
- `formatter_failures`
- `migration_state` (`IDLE`, `IN_PROGRESS`, `FAILED`, `NOT_APPLICABLE`)
- `redaction_failures`
- `schema_version`
- `privacy_generation`
- `rejected_context`
- `telemetry_last_result` (`DISABLED`, `SENT`, `FAILED`, `SKIPPED`)

Recursion rule:

- The writer that persists product-health must not pass through the customer observation hook.
- If a diagnostic write fails, increment one in-memory counter and stop. Do not emit a customer event, and do not emit a new diagnostic per failure in a loop.
- Node already captures `fetch` before patching so the telemetry ping does not re-enter the interceptor (`telemetry.cjs` lines 27–36). The same pattern is required for any future store client: the store write is not an observed destination.

A future local UI, if it exists, must not render these rows on the customer timeline. That UI is not authorized here.

## 2. Failure taxonomy

| Failure | Issue location | Customer-visible evidence | Application effect |
| --- | --- | --- | --- |
| Hook did not install | `OPTICS` | Coverage gap on the run envelope | Process continues without observation |
| Event rejected by allowlist | `OPTICS` | Drop count. The secret is absent | Call returns normally |
| Queue or disk could not accept an event | `OPTICS` or `ENVIRONMENT` | Explicit drop count. Not a silent gap | Call returns normally |
| Store corrupt | `OPTICS` | Integrity failure. Store file kept | Call returns normally |
| Provider HTTP 4xx/5xx | `PROVIDER_INTERACTION` or `UNKNOWN` | `application_status` `APPLICATION_ERROR` | The application’s own error |
| DNS, connect, TLS, timeout | `NETWORK` | `failure_kind` and unavailable HTTP status | The application’s own error |
| Wrapped application exception | `CUSTOMER_APPLICATION` | `error_class` type name only | The application’s own exception |
| Unsupported client | `COVERAGE` | `UNSUPPORTED` or no row | No change |
| Reader cannot parse a legacy file | `OPTICS` | Corrupt count. File kept | Not an application failure |
| Context rejected | `CONFIGURATION` | Null trace fields plus `rejected_context` | Call returns normally |

`OPTICS_ERROR` remains the display token when Optics itself could not complete a local operation (unreadable data, signal on the wrapper). It is not used as the application outcome for a provider 500.

## 3. Fail-open invariant

For the Optics observation path:

- A failure, exception, or killed observation thread must not fail the application call, must not hang it, and must not change response bytes or status.
- Optics must not fabricate a successful observation when the write did not happen.
- Optics must not fabricate a successful application outcome.

Exceptions, explicit and narrow:

1. **Privacy.** If the only way to proceed inside Optics would persist a prohibited value, Optics drops the field or the event. It still does not change the application response.
2. **Local safety.** If a path escapes the evidence root or a symlink would write outside that root, Optics refuses that write. It still does not change the application response.

Enforcement that blocks, redacts, or caps a call is Phantom Engine behavior co-located in the current interceptor. It is not an exception to Optics fail-open, because it is not Optics. This contract does not extend those branches. Free mode today already fails open on policy fetch (`interceptor.cjs` lines 341–344) and swallows log-write errors. Paid-mode blocking is outside this invariant’s grant of permission.

Hang: any future store call made on the application’s request path needs a timeout. The timeout number is `NOT_SET`. Until it is set, an implementation Force must not put an unbounded lock on the request path. The current design writes at exit, which avoids per-call lock waits and loses the buffer if the process is killed. Both facts stand.

## 4. Nonfunctional budgets

Copied as architecture fields. Targets are not filled in.

| Budget ID | Category | Current target | Target status | Failure behavior in one line |
| --- | --- | --- | --- | --- |
| `NFR-STARTUP` | startup | `NOT_SET` | `NOT_SET` | Application start continues if observation cannot start |
| `NFR-INTERCEPTOR-INIT` | interceptor init | `NOT_SET` | `NOT_SET` | Failed hook install is disclosed and does not change application output |
| `NFR-PER-CALL-OVERHEAD` | per-call overhead | `NOT_SET` | `NOT_SET` | Observation failure leaves application output unchanged |
| `NFR-MEMORY` | memory | `NOT_SET` | `NOT_SET` | Pressure uses the queue rules; loss is explicit |
| `NFR-WRITE-LATENCY` | write latency | `NOT_SET` | `NOT_SET` | Failed write is disclosed; the application continues |
| `NFR-QUEUE-CAPACITY` | queue capacity | `NOT_SET` | `NOT_SET` | Drops are explicit |
| `NFR-DATABASE-SIZE` | database size | `NOT_SET` | `NOT_SET` | A configured limit is explicit; unset means unbounded retention |
| `NFR-QUERY-LATENCY` | query latency | `NOT_SET` | `NOT_SET` | Over-budget query is refused |
| `NFR-UI-QUERY-RENDER-LATENCY` | UI render | `NOT_SET` | `NOT_SET` | A failed query is not a healthy current view. UI is not in this Force |
| `NFR-EXPORT-TIME` | export | `NOT_SET` | `NOT_SET` | Partial export is not renamed into place |
| `NFR-SHUTDOWN-FLUSH` | shutdown flush | `NOT_SET` | `NOT_SET` | Lifecycle state is explicit |
| `NFR-DROPPED-RECORD` | dropped record | `NOT_SET` | `NOT_SET` | One drop notice, no payload, no storm |

Measurement method, workload, percentile, release gate, and evidence reference are `NOT_SET` for every row. Privacy impact is the A1 allowlist.

## 5. Overload and backpressure

- Default sampling policy is `UNSAMPLED`. Every accepted event is in the store, or an explicit drop exists.
- If a future sampling policy is introduced, each event records the policy id and the probability, and views must not call the result complete. This pack does not introduce sampling.
- Error, slow-call, and proof-critical preservation under sampling is unspecified until that policy exists. No percentile defines “slow” (`NOT_SET`).
- Queue-full behavior: refuse further observation inserts, add one `events_dropped` increment by the number refused, keep the application moving.
- Burst behavior: same as queue-full. No second customer event per dropped call.
- Database-size behavior: with no customer limit, the store grows and product-health exposes `database_size_bytes`. With a customer limit, the writer stops accepting new rows and records the stop. It does not delete old rows to make room. Deletion is the retention manifest in A2.

## 6. Clock and crash consistency

- Canonical timestamps are UTC RFC3339.
- Duration uses a monotonic clock when the runtime provides one (`perf_counter` / `process.hrtime`). Wall clock is only a fallback and must set `clock_quality` to `WALL_CLAMPED` and must not store a negative duration.
- Display timezone is a future UI concern. Stored values stay UTC. This Force does not add the UI.
- Tied timestamps order by `sequence`, then `event_id`.
- Clock rollback and DST do not rewrite stored instants.

Lifecycle of a run envelope and of an event:

| State | Meaning |
| --- | --- |
| `COMPLETE` | The writer closed the record after a normal exit flush |
| `PARTIAL` | Some calls were durable and the writer knows others were still buffered |
| `INTERRUPTED` | Exit hook or migration stopped before the planned flush. Crash, signal, or disk error |
| `ABANDONED` | Process ended with no flush and no partial durable events for that `run_id` |
| `RECOVERED` | A later open found a partial transaction or partial file and made it readable without deleting it |

Today’s writers have none of these states. A normal exit that finishes `writeFileSync` is implicitly complete and unlabeled. `SIGKILL` is unlabeled absence. The contract adds the labels. It does not claim current files can be reconstructed into `ABANDONED` after the fact.

Sleep and resume: duration must not use a clock that includes suspend if a monotonic clock that excludes it is available. If that cannot be determined, `clock_quality` is `UNAVAILABLE` and `duration_ms` is null rather than a misleading number.

## 7. Freshness

For a future view:

- `CURRENT` — store readable, last successful write within a window. The window number is `NOT_SET`, so implementations must not invent one. Until it is set, `CURRENT` is not emitted. Use `UNKNOWN`.
- `HISTORICAL` — the query range ends before the newest durable event.
- `STALE` — reserved until the freshness window is set.
- `UNKNOWN` — the default honest value, including this entire pre-implementation period.

Completeness of a run is the lifecycle field, not a percentage.

## 8. Indicators, not SLOs

Call rate, error rate, duration, in-progress work, retries, queue depth, drops, write latency, unknown outcomes, and coverage gaps may exist later as indicators. None is an SLO. An SLO exists only after a customer sets a target and a window. This pack does not create that configuration.

Optics product-health indicators stay separate from provider outcomes. A provider 500 is not an Optics failure. An Optics write failure is not a provider failure.

## 9. Alerting

Not selected. Options named by the roadmap (run-time, post-run, external scheduler, explicit service) stay `NEEDS_FOUNDER_DECISION`. A daemon is not the default. This Force does not add an alerter. Privacy-invariant failure and evidence-write failure are the highest-severity candidates if alerting is ever chosen. That sentence is a priority note, not an implementation.

## 10. Background update

No background auto-update. Registry lookup stays the existing explicit `vantio status --check-registry` behavior. This pack does not add a periodic check.

## 11. Non-executable illustration

`NON_EXECUTABLE_ARCHITECTURE_EXAMPLE`

```text
on observation failure:
  do not alter the application response
  if the failure would have written a secret: drop the write, count redaction_failures, stop
  if the path leaves the evidence root: drop the write, count integrity failure, stop
  else: count events_dropped once, stop
  do not enqueue another customer event to describe the drop
```
