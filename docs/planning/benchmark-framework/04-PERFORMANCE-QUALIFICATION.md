# Performance qualification scaffold

Audience: INTERNAL_RESTRICTED

Normative rows: `PERFORMANCE-SCAFFOLD.json`.

## Result rule

A metric is `MEASURED` only when the record has an instrument, a workload, a start time, a sample count, and a result value taken from that run. Anything else is `NOT_MEASURED`.

This force took no measurements. Every row is `NOT_MEASURED`. `result_value` is null. `estimate` is `PROHIBITED`.

`NOT_SET` on an architecture budget is a target posture. It is not a measured result, and it is not converted into a number here.

The roadmap example in `docs/internal/optics-best-in-class-roadmap.md` section 6 item 14 is `NOT_ADOPTED`. `NFR-PER-CALL-OVERHEAD` remains `NOT_SET` in `docs/architecture/optics-foundation/06-SELF-OBSERVABILITY-AND-RELIABILITY.md`.

## Metrics

| Id | Question when a later force measures it |
| --- | --- |
| `cpu` | Processor time added while the product is active |
| `memory` | Resident memory added while the product is active |
| `disk` | Disk bytes added while the product is active |
| `evidence_growth` | Evidence bytes added over a named interval |
| `startup` | Time until the wrapped workload is usable |
| `policy_load` | Time to load the policy under test |
| `decision_latency` | Time to return one allow, observe, or deny decision |
| `connection_latency` | Time to establish the connection under test |
| `throughput` | Completed events in a named interval |
| `event_loss` | Events the design says were dropped or never written |
| `backpressure` | Queue depth or refused inserts under a named load |
| `reboot_recovery` | Time and outcome after a reboot of the host under test |
| `degradation_recovery` | Time and outcome after a stated degradation |
| `rollback` | Time and outcome of the named rollback procedure |
| `uninstall` | Time and outcome of the named removal procedure |

## Where the numbers bind

`performance` and `operational_overhead` set `measurement_blocks_from_order` to 2. Those dimensions cannot pass `PRODUCTION_GRADE_INTERNAL_CANDIDATE` while a required metric is `NOT_MEASURED`.

Every other dimension sets the measurement gate at order 5, `INDEPENDENTLY_BENCHMARKED_CANDIDATE`.

The checker command in `00-PROGRAM-BOUNDARY.md` exits on the scaffold's shape. That exit is not a value for any metric above.
