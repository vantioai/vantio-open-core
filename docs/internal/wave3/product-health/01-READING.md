# Product health reading

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

`productHealth(runtime)` reads a Phantom Engine integrated runtime and returns a `W3_PRODUCT_HEALTH_FAILURE_TRUTH` record. `snapshot` stores the same record on `product_health`.

## Planes

| Token | Plane while host attachment is false |
| --- | --- |
| Shared health state, including `HEALTHY_ENFORCING` | `OBSERVATION` |
| `BLOCKED_HOST` | `DECISION` |
| `ENFORCE` | `DECISION` |
| `PROMOTED_MATCH` | `DECISION` |

`reported_as_host_enforcement` is taken from the contribution's host plane. A host plane status equal to the token, `APPLIED`, or `applied: true` is reported as host enforcement and the reading code becomes `HONESTY_FAULT`. The field is left as recorded. The function does not rewrite it to false.

`HEALTHY_ENFORCING` keeps failure classification `fail_closed` with basis `TOKEN_MEANING` when the shared health quote carries those fields. `HEALTHY_OBSERVING` keeps `fail_open` the same way. `BLOCKED_HOST`, `ENFORCE`, and `PROMOTED_MATCH` have failure classification null. They are decision labels, and this reading does not assign them a shared health failure class.

## Rollup

| Evidence in the runtime | `product_state` |
| --- | --- |
| No shared health contribution | `EVIDENCE_UNAVAILABLE` |
| One shared health state | That state |
| Two or more different shared health states | `ENFORCEMENT_UNKNOWN`, with each input state in `visible_states` |
| A health quote whose state is outside the twelve | `ENFORCEMENT_UNKNOWN`, with the raw value in `visible_evidence` |

`healthier_token_selected` is false. `product_success` is false. `success_emitted` is false. `green` is false. `optimistic_success` is false.

A request that sets `success`, `green`, or `product_success`, or that asks for a healthy token while the derived state is outside the healthy pair, returns `OPTIMISTIC_SUCCESS_REFUSED` and keeps the derived state. A request that sets an attachment flag returns `ATTACHMENT_REFUSED`. The runtime's `host_attachment` stays false.

## Ceiling

`execution_ceiling` is `HOST_ATTACHMENT_FALSE`. `ceiling_raised` is false. `eligible_plane` is the packet's `plane_id`. On this starting commit that value is `NONE`, `named_eligible_plane` is false, and `infra_requirement` is `W3-INFRA-REQ-1`.

`visible_evidence` always includes freshness `UNKNOWN` and independent verification `NOT_INDEPENDENTLY_VERIFIED`. Absent planes are listed with evidence `MISSING`.
