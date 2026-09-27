# State separation

Audience: INTERNAL_RESTRICTED

The planes are `OBSERVATION`, `DECISION`, `APPLICATION_ENFORCEMENT`, `HOST_ENFORCEMENT`, `CONTAINMENT`, `REVOCATION`, `EVIDENCE`, and `INDEPENDENT_VERIFICATION`. Every contribution includes all eight. Absent work stays `ABSENT` except independent verification, which is always `NOT_INDEPENDENTLY_VERIFIED`.

| Capability | Wave 2 state cited | Execution on this runtime | How to read the result |
| --- | --- | --- | --- |
| Shared health | `IMPLEMENTED_INTERNAL` | `EVALUATE_ONLY` | `HEALTHY_ENFORCING` and `HEALTHY_OBSERVING` are catalog tokens. `audit.green` stays false. The token is not a latch |
| Ingress | `MERGED_OBSERVE_ONLY_LOADER_UNTOUCHED` | `EVALUATE_ONLY` | `OBSERVED_ONLY` is observation. `HELD` and `REFUSED` are decisions. `packet_effect` stays `NOT_APPLIED` |
| Egress application path | `MERGED_CONTRACT_ONLY_HOST_NETWORK_NOT_EXECUTED` | `EVALUATE_ONLY` | `live_wire_action` is quoted as `would_wire_applied: false`. The application plane stays `NOT_APPLIED` or `GAP` |
| Egress host path | `MERGED_CONTRACT_ONLY_HOST_NETWORK_NOT_EXECUTED` | `CONTRACT_ONLY` | Supplied host observations stay contract rows. `this_force_executed_host` stays false |
| Host authority | `CONTRACT_ONLY` | `CONTRACT_ONLY` | `DENIED_BY_CITED_MECHANISM` may quote `EACCES` and sets `cited_effect_applied` false. `kernel_executed` stays false |
| Process lineage | `MERGED_EVALUATE_ONLY_HOST_ATTACHMENT_FALSE` | `EVALUATE_ONLY` | Envelope lineage is evaluated. It is not an operating-system process tree |
| Descendant host | `CONTRACT_ONLY` | `CONTRACT_ONLY` | Fork inherit is a contract row on the descendants surface. No child process is spawned |
| Descendant grant | `MERGED_EVALUATE_ONLY_HOST_ATTACHMENT_FALSE` | `EVALUATE_ONLY` | An `ALLOW` subset grant does not attach a descendant |
| Sequential and aggregate | `MERGED_EVALUATE_ONLY_HOST_ATTACHMENT_FALSE` | `EVALUATE_ONLY` | `enforcement` stays `EVALUATE_ONLY`. `host_attachment` stays false |
| Progressive | `MERGED_IN_PROCESS_HOST_ATTACHMENT_NOT_PERFORMED` | `HOST_ATTACHMENT_FALSE` | Stage `ENFORCE` and class `PROMOTED_MATCH` stay in-process. `applied_to_host` stays false |
| Policy versioning | `RECORDED_NOT_APPLIED` | `NOT_PERFORMED` | Version ids are stored. Kernel maps are unchanged |
| Evidence | `RECORDED_NOT_INDEPENDENTLY_VERIFIED` | `NOT_PERFORMED` | Local rows only |
| Revocation | `RECORDED_NOT_HOST` | `EVALUATE_ONLY` | Ingress `idp_revoke` stays `NOT_EXECUTED`. Envelope revoke updates the returned catalog only |
| Rollback | `RECORDED_NOT_HOST` | `EVALUATE_ONLY` | Ingress rollback mints a session version and drops grants. Progressive rollback clears the in-process active set |
| Uninstall | `NOT_PERFORMED` | `NOT_PERFORMED` | Recorded, not executed |

Containment from an ingress child-escape is `DECISION_RECORDED_ONLY` with execution `NOT_PERFORMED`. `cgroup_freeze_applied` stays false.

Prior governance text says the shared health package had no Phantom Engine runtime integration. This composition cites health records inside the runtime and still does not treat them as Phantom enforcement. The citation does not close that limitation.
