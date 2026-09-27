# Measurement method

Audience: INTERNAL_RESTRICTED

Normative rows: `PERFORMANCE-REGISTER.json`.

The result rule is the Wave 2 rule. A metric is `MEASURED` only when the record has an instrument, a workload, a start time, a sample count, and a result value taken from that run. Anything else is `NOT_MEASURED`. `estimate` stays `PROHIBITED`.

The qualifier is `scripts/qualify.mjs`. It calls `createRuntime` and `integrate` in `internal/pe-integrated-runtime`. It does not call host proof entry points. The runtime clock is the default `() => 0`.

Percentiles use nearest rank: sort the sample, rank `ceil(p/100*n)`, and take that observation. They describe this sample. They are not a population tail.

The shared workload is one egress application decision:

| Field | Value |
| --- | --- |
| `op` | `egress` |
| `path.id` | `app_fetch` |
| `policy.blocked_hosts` | `evil.example` |
| Destination | `evil.example:443` `https`, `in_product_scope` true |
| Expected `quote.result` | `DENIED` |
| `would_wire_applied` | false |
| `this_force_executed_network` | false |
| `host_attachment` | false |

`attempt.policy_loaded: true` is a field on that caller-supplied attempt. It is not a timed policy load.

## Measured metrics

### `decision_latency`

Instrument: `process.hrtime.bigint` around `integrate` only. Each counted sample uses a fresh runtime created outside the timer. Warmup calls are excluded. `result_value` is the nearest-rank p50 in nanoseconds. No timer overhead is subtracted.

Wall-clock nanoseconds for one in-process egress application DENIED decision on a fresh runtime. The timer wraps integrate only. The decision does not apply a wire action. Sample percentiles describe this run. This is not an SLO and it does not move a claim stage.

### `throughput`

Instrument: `process.hrtime.bigint`. One warmup window is excluded. Each counted window loops `integrate` on one runtime until the call that crosses the target duration. `window_ns` is the actual elapsed time and includes that call. A disposition guard runs inside the window. `result_value` is the completed-decision count of the nearest-rank p50 window when windows are ordered by `completed / window_ns` using integer cross-multiplication.

Completed in-process egress application DENIED decisions in one measured window. Nearest-rank percentiles use the counted windows only. They are sample percentiles, not a population tail, not network throughput, and not an SLO.

### `evidence_growth`

Instrument: `Buffer.byteLength(JSON.stringify(evidence_row), "utf8")` summed across the rows appended by a fixed decision count on a fresh runtime. The runtime clock returns 0. Repetitions must produce the same byte count; a spread aborts the run. `result_value` is that byte count. Storage is the in-memory evidence list.

UTF-8 JSON bytes of the in-memory evidence rows appended by a fixed count of egress application DENIED decisions. The runtime clock returns 0, so the bytes do not include a wall-clock timestamp. This is not disk growth and not an independent verification.

## Unmeasured metrics

`cpu`: The metric asks for processor time added while the product is active. This run did not attach the product. The selected eligible plane is NONE. process.cpuUsage of the qualifier process was not used as this metric.

`memory`: The metric asks for resident memory added while the product is active. This run did not attach the product. The selected eligible plane is NONE. process.memoryUsage of the qualifier process was not used as this metric.

`disk`: The metric asks for disk bytes added while the product is active. This run did not attach the product and did not write a product data directory. A zero was not recorded.

`startup`: The metric asks for time until the wrapped workload is usable. The integrated runtime does not wrap a workload. createRuntime was not timed as a substitute.

`policy_load`: The metric asks for time to load the policy under test. The runtime receives a caller-supplied policy object and records policy versions in memory. It does not load a policy. No load was timed.

`connection_latency`: The metric asks for time to establish the connection under test. The runtime does not open a connection. this_force_executed_network stays false. No connection was opened.

`event_loss`: The metric asks for events the design says were dropped or never written. This run did not execute a drop-inducing workload. A zero taken from the successful egress path would restate that path. It was not recorded.

`backpressure`: The metric asks for queue depth or refused inserts under a named load. The runtime has no queue and no refused-insert counter. Queue depth was not observed. A zero was not recorded.

`reboot_recovery`: The metric asks for time and outcome after a reboot of the host under test. No reboot was performed. The eligible plane is NONE. W3-INFRA-REQ-1 was not provisioned.

`degradation_recovery`: The metric asks for time and outcome after a stated degradation. No degradation was executed.

`rollback`: The metric asks for time and outcome of the named rollback procedure. rollback_ingress records rolled_back_not_granted and does not apply a host rollback. That call was not timed as the procedure.

`uninstall`: The metric asks for time and outcome of the named removal procedure. The uninstall operation records RECORDED_NOT_PERFORMED and refuses performed execution. The removal was not executed and was not timed.

## Command

From the repository root, after the tree that will be cited is committed:

`node docs/internal/wave3/performance/scripts/qualify.mjs --write`

The process records `git rev-parse HEAD` and `uname -srm` before it writes. Cursor environment ids are copied only from `CURSOR_ENVIRONMENT_PUBLIC_ID`, `CURSOR_ENVIRONMENT_VERSION_PUBLIC_ID`, and `CURSOR_ENVIRONMENT_BUILD_ID`. When those variables are absent, the register stores `NOT_OBSERVED`.
