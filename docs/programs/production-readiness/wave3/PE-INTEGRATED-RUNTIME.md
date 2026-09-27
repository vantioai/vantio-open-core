# Phantom Engine integrated runtime

Audience: INTERNAL_RESTRICTED

This track composes the merged Wave 2 Phantom Engine evaluators into one in-process runtime. The runtime quotes those evaluators. It does not attach them to a host.

| Plane | What a row means here |
| --- | --- |
| `OBSERVATION` | A supplied fact or an observe-only authority result |
| `DECISION` | An evaluator disposition, including allow, deny, hold, and refuse |
| `APPLICATION_ENFORCEMENT` | Present so the plane stays visible. Status is `NOT_APPLIED` or `GAP`. The interceptor is not called |
| `HOST_ENFORCEMENT` | Present so the plane stays visible. Status is `NOT_APPLIED` or `GAP`. `kernel_executed` stays false |
| `CONTAINMENT` | A recorded containment decision. No cgroup freeze runs |
| `REVOCATION` | A session, envelope, or in-process revoke record. Identity-provider revoke stays unexecuted |
| `EVIDENCE` | A local row. It is not an independent verification |
| `INDEPENDENT_VERIFICATION` | Always `NOT_INDEPENDENTLY_VERIFIED` |

A decision row does not fill an enforcement plane. A contract row does not become kernel enforcement. An unattached mechanism does not become active protection.

`HEALTHY_ENFORCING` from the shared health runtime stays a catalog token. `PROMOTED_MATCH` from progressive enforcement stays an in-process label. `DENIED_BY_CITED_MECHANISM` stays a contract disposition. `BLOCKED_HOST` on an egress decision is a wire label for a path this runtime did not execute.

Success token for this force: `W3_PE_INTEGRATED_RUNTIME_READY_FOR_COUNCIL`.

Council status: `PENDING_INDEPENDENT_COUNCIL`.
