# Claim stage ladder

Audience: INTERNAL_RESTRICTED

Producer classification: `BENCHMARK_FRAMEWORK_READY_FOR_COUNCIL`

Normative list: `CLAIM-LADDER.json`. The stages below are the only statuses a cell may use, in this order.

| Order | Stage | What the evidence shows |
| --- | --- | --- |
| 1 | `BEST_IN_CLASS_DESIGN_TARGET` | A written design names the product, the behavior, the non-goals, and the evidence required before an internal production candidate. Numbers are founder-set or left `NOT_SET` / `NOT_MEASURED`. |
| 2 | `PRODUCTION_GRADE_INTERNAL_CANDIDATE` | Stage 1 is satisfied, and an internal run of that design's implementation is on record. |
| 3 | `CLEAN_HOST_PROVED_CANDIDATE` | Stage 2 is satisfied, and the same checks passed on a clean host whose evidence tier is set. |
| 4 | `PROVED_EXTERNAL_CANDIDATE` | Stage 3 is satisfied, and a verifier outside the producing team recorded the result. |
| 5 | `INDEPENDENTLY_BENCHMARKED_CANDIDATE` | Stage 4 is satisfied, and every required metric for the dimension is `MEASURED` by a party other than the implementation producer. |
| 6 | `CUSTOMER_VALIDATED_CANDIDATE` | Stage 5 is satisfied, and a customer workload and window are named. |
| 7 | `EVIDENCE_BACKED_BEST_IN_CLASS` | Stage 6 is satisfied, and a comparator against documented peer capabilities meets the design target with limitations still stated. |

## Skip rule

`SATISFIED` at order n requires `SATISFIED` at orders 1 through n-1. The status of a stage the evidence does not meet is `NOT_REACHED`. There is no skip status.

`current_stage` is the last consecutive `SATISFIED` stage, or `NONE` when stage 1 is `NOT_REACHED`.

`blocked_by` on a later `NOT_REACHED` stage names the first `NOT_REACHED` stage. The first gap itself has `blocked_by` null.

## What does not advance a stage

| Input | Effect |
| --- | --- |
| A checkmark in `docs/PRODUCT_LINEUP.md` | `DOES_NOT_SATISFY_ANY_STAGE` |
| A document council pass | Can support stage 1 when the design checklist is met. It does not fill stages 2 through 7. |
| `docs/planning/clean-host-lifecycle/` with `evidence_tier` `UNSET` | Does not fill `CLEAN_HOST_PROVED_CANDIDATE` |
| A coverage-matrix row with `this_force` `NOT_EXECUTED` | Does not fill any stage |
| `NOT_MEASURED` | Blocks stage 5, and blocks stage 2 on the performance and operational-overhead dimensions |
| An example latency figure in the roadmap | `NOT_ADOPTED` |

## Slots

| Slot | Blocks from order |
| --- | --- |
| `internal_candidate_record` | 2 |
| `clean_host_record` | 3 |
| `independent_verifier` | 4 |
| `benchmark_record` | 5 |
| `customer_window` | 6 |

Every slot in the initial matrix is `NOT_PRESENT`.
