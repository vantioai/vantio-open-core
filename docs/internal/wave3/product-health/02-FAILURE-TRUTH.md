# Failure truth

Audience: INTERNAL_RESTRICTED

Producer classification: `W3_PRODUCT_HEALTH_FAILURE_TRUTH_READY_FOR_COUNCIL`

Failure truth is the shared health failure classification when the quote has one, plus the visible gap when evidence is missing, unavailable, or unknown.

| Situation | What the reading keeps visible |
| --- | --- |
| No `health` contribution | `product_state` `EVIDENCE_UNAVAILABLE`, evidence `MISSING` |
| Shared health state `EVIDENCE_UNAVAILABLE` | That state, evidence `UNAVAILABLE` |
| Shared health state `ENFORCEMENT_UNKNOWN` | That state, evidence `UNKNOWN` |
| Process up or HTTP 200 with no protection fact | `ENFORCEMENT_UNKNOWN` from the shared health runtime |
| Disagreed protection facts | `ENFORCEMENT_UNKNOWN` and every input state in `visible_states` |
| Freshness | `UNKNOWN` on every reading |
| Independent verification | `NOT_INDEPENDENTLY_VERIFIED` |
| Eligible plane packet | `plane_id` and requirement id copied from `BLOCKED-INFRA.json` |

`missing_evidence_collapsed_to_success`, `unknown_evidence_collapsed_to_success`, and `unavailable_evidence_collapsed_to_success` are false.

`BLOCKED_HOST` remains the egress decision quote `live_wire_action`. The decision status stays the evaluator result. The host plane stays unapplied. The application plane stays unapplied.

`ENFORCE` remains the progressive stage on the decision plane. `PROMOTED_MATCH` remains the progressive decision class on the decision plane. `applied_to_host` on that quote stays false.

A catalog token `HEALTHY_ENFORCING` can sit on `OBSERVATION` with `audit.green` false. That observation is the shared health token. The host plane for that contribution stays `NOT_APPLIED` with execution `HOST_ATTACHMENT_FALSE`. The product rollup uses that observation as `product_state` and sets `product_plane` to `OBSERVATION`. `healthy_enforcing_reported_as_host_enforcement` stays false.

Track 5 has no named eligible plane in the blocked-infrastructure packet. This composition does not treat a future plane name as permission to attach. `ceiling_raised` stays false for any packet value this function reads.
