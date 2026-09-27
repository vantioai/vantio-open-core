# Pending council

Audience: INTERNAL_RESTRICTED

| Field | Value |
| --- | --- |
| `council_status` | `PENDING_INDEPENDENT_COUNCIL` |
| `council_verdict` | null |
| `self_certified_council_pass` | false |
| Producer classification | `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL` |

This slot is empty. The producer classification means the reading is ready for a separate council. It does not record a council pass.

Questions left for that council:

| Question | Answer |
| --- | --- |
| May a quoted `HEALTHY_ENFORCING` remain the product state on `OBSERVATION` while the host plane stays `NOT_APPLIED`? | `PENDING` |
| When two shared health states disagree, is the rollup `ENFORCEMENT_UNKNOWN` with both states kept in `visible_states`? | `PENDING` |
| Do `BLOCKED_HOST`, `ENFORCE`, and `PROMOTED_MATCH` stay decision citations with a null failure classification? | `PENDING` |
| Does the ceiling stay `HOST_ATTACHMENT_FALSE` while the eligible plane packet says `NONE` and `W3-INFRA-REQ-1`? | `PENDING` |

`CLEAN_HOST_INTERNAL_PROOF` and `PROVED_EXTERNAL` stay false. Host attachment status stays `HOST_ATTACHMENT_FALSE`.
