# Authority contract

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

`evaluateIngress(evidence, session)` reads one bundle and returns one decision. It does not read `/proc`, the network, or a loader map.

## 1. Hold

`permitted_after_accept` requires all of the following:

- Workload `enroll_id` present and `cgroup_id` not `0`
- Listener class `expected` for that workload, protocol, port, bind, and comm when the envelope row sets them
- Owner pid, start time, and comm equal the identity. Trace id equal on the workload, the identity, and the accept
- Caller window set and `attested_at_ms` inside it. Shared freshness remains `UNKNOWN`
- Executable digest present and equal to the expected digest
- Version equal when version binding is required, which is the default
- Image digests equal when the envelope sets `requires_image_binding`
- Policy present, version not `missing` / `unversioned` / `unknown` / `none`, and `policy_sha`, `applied_sha`, and `candidate_sha` equal
- Health loader, evidence, enroll, netns, and trace map all true, coverage `seeing`, protection echo not a withholding state
- Accept mechanism is not `io_uring`, protocol is not UDP, and the accepting pid and start time match the identity
- Later behaviors, if any, share the trace and the cgroup and set `authorized` true

Anything short of that list does not hold.

## 2. Refuse

| Condition | Reason |
| --- | --- |
| Input asks to mutate the live loader | `live_loader_mutation_refused` |
| Same pid, different start time, comm, or trace | `impersonation` |
| Listener owner pid differs | `wrong_process` |
| Executable digest differs | `modified_executable` |
| Both image digests present and they differ | `image_binding_mismatch` |
| Required version differs | `version_binding_mismatch` |
| Valid credential `bound_workload_id` differs | `valid_credential_wrong_workload` |
| Presented credential does not validate | `credential_invalid` |
| Listener class `unexpected` | `unexpected_listener` |
| Behavior cgroup differs, or kind `cgroup_escape` | `child_process_escape` |
| Behavior `authorized` is not true | `post_accept_denied` |
| Session key was revoked, including after an escape or a deny | `revoked` |
| `replay_grant_id` is in the dead set | `grant_not_carried` |

`post_accept_denied` and `child_process_escape` set `containment.required` true and `effect` `DECISION_RECORDED_ONLY`.

## 3. Withhold

| Condition | Reason |
| --- | --- |
| Bundle is not an object | `evidence_malformed` |
| Unix, vsock, UDP accept, `io_uring`, Docker DNS `127.0.0.11` | `unsupported_path` |
| Loader, evidence, netns, trace map, or coverage `cannot_see` | `health_or_evidence_unavailable` |
| Coverage or protection state `degraded` | `health_degraded` |
| Coverage `honest_idle` while an accept is present | `health_evidence_contradiction` |
| No `enroll_id` | `not_enrolled` |
| Cgroup id `0` or empty | `unattributable_cgroup` |
| Protection echo `quarantined` | `already_quarantined` |
| Restart or rollback with no last-known digest | `recovery_required` |
| Policy missing, version empty, or sha mismatch, including after rollback until the new version id is supplied | `stale_policy` |
| Accepting pid is a different process | `unattributed_accept` |
| Attestation outside the caller window, or protection echo `protection_stale` | `stale_identity` |
| Window absent, or pid, start time, comm, or trace missing | `identity_unknown` |
| Executable digest absent, or a required image or version digest absent | `integrity_unknown` |
| Authority claim is `credential`, or a valid credential has no integrity binding | `credential_is_not_integrity` |
| Later behavior trace differs | `post_accept_unjoined` |
| Authority claim is `reachability` | `reachability_is_not_authority` |

## 4. Observation only

| Condition | Reason |
| --- | --- |
| Expected listener, no accept, no withholding finding | `expected_listener_is_not_authority` |
| Undeclared listener, including an empty envelope | `undeclared_listener_is_not_authority` |
| Declared listener with no listener object in this bundle | `missing_listener_is_not_authority` |
| Restart reloaded a last-known digest | `policy_reloaded_not_granted` |
| Rollback minted a new version id | `rolled_back_not_granted` |

## 5. Fixed result flags

Every result sets `live_loader_mutated` false, `live_bind_refused` false, `reachability_is_authority` false, `credential_is_integrity` false, `ingress_protected_claim` false, `packet_effect` `NOT_APPLIED`, `evidence_decision` `observed`, `freshness` `UNKNOWN`, `idp_revoke` `NOT_EXECUTED`, `stranger_host_executed` false, and `customer_deployed` false.

The result has no `ActionTaken` field. It does not emit `ALLOWED` or `BLOCKED`.
