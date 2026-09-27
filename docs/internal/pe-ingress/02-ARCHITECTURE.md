# Architecture notes for council

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

These notes are the producer's architecture. They are not a council verdict. A separate council accepts or rejects them.

## 1. Planes

| Plane | This program | Live loader on the cited tip |
| --- | --- | --- |
| Evidence | `evidence_decision` `observed` | P0b `decision=observed` |
| Packet | `packet_plane` `OBSERVE_ONLY`, `packet_effect` `NOT_APPLIED` | No inbound drop |
| Authority | `HELD`, `REFUSED`, `WITHHELD`, `OBSERVED_ONLY` | No post-accept authority object |
| Protection state | Echo of a supplied name, `ingress_protected_claim` false | Nine states in `pe_protection_state.py`. `protected` is not an ingress proof |

`HELD` means the supplied bundle bound an enrolled identity, an executable digest, a current listener policy, an in-window attestation, a healthy evidence path, and an accepted connection whose later rows stayed inside that binding.

`HELD` does not mean the kernel allowed a packet, the protection state became `protected`, or a credential was accepted as integrity.

## 2. Decisions the council is asked to review

1. Post-accept authority lives in this private open-core package. The private loader stays on P0b observe. This force does not patch it to satisfy tests.
2. An expected listener is `OBSERVED_ONLY`. Listening is not authority. A reachability claim is `WITHHELD` with `reachability_is_authority` false.
3. A presented credential is not integrity. A valid credential bound to a different workload is `REFUSED` even when the executable digest matches.
4. Unknown, stale, or missing identity, integrity, policy, or health is `WITHHELD` or `REFUSED`. It does not widen the grant. A missing caller window stays `identity_attestation` `WINDOW_ABSENT` and shared freshness `UNKNOWN`.
5. An unexpected listener is `REFUSED` on the authority plane. `live_bind_refused` stays false, matching P0b: unexpected is named, and the bind is not refused in kernel.
6. Unauthorized post-accept behavior and a cgroup escape are `REFUSED` when they are the primary reason. When `child_process_escape` or `post_accept_denied` is present under a higher-precedence reason, containment is still `DECISION_RECORDED_ONLY` with executor `NOT_WIRED_IN_LIVE_LOADER`. The same record is written when `accept` is null and when the behavior list is a single object or `post_accept` itself is an array. The cited quarantine executor is unwired. This program does not pretend a freeze ran.
7. Revoke, restart, and rollback drop session grants. Restart and rollback keep the last-known policy digest or return `recovery_required`. They mint no silent grant and they do not set `protected`. Rollback uses a new version id of the form `rollback:<sha>:<n>`.
8. Unix-domain, vsock, UDP peer attribution, `io_uring` accept, Docker embedded DNS `127.0.0.11`, and cgroup id `0` are unsupported or unattributable. Authority is withheld. Image digest absence is a named partial unless the policy requires the binding.
9. `fail_mode` `fail_closed` records `fail_closed_packet_plane_not_authorized` and still applies no packet effect. The feasibility file leaves a fail-closed inbound default to a separate founder decision.
10. Join of a later open, exec, or egress row to an accept is association. `association_not_causation` is true whenever an accept is present. The result does not copy behavior paths.

## 3. Precedence

The first matching reason in `PRECEDENCE` wins. Health and unsupported paths outrank identity. Identity contradictions outrank integrity. Integrity outranks credential and listener class. Listener class outranks post-accept behavior. A dead grant outranks a new hold. `permitted_after_accept` is last and is the only `HELD` reason.

A second workload's expected rows do not become this workload's unexpected alarm. That preserves the P0b rule that an empty or other-workload envelope stays undeclared.

## 4. What a pass would not authorize

Acceptance of this branch, if a later council records one, would accept the in-process contract. It would not authorize a loader edit, an inbound drop, a customer deploy, a stranger-host run, a protection-state change, or a public ingress claim.
