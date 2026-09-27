# Unsupported paths, health, and freshness

Audience: INTERNAL_RESTRICTED

Producer classification: `PE_INGRESS_PROGRAM_READY_FOR_COUNCIL`

## 1. Unsupported or partial

| Input | Result |
| --- | --- |
| Protocol `unix`, `unix-domain`, or `vsock` | `unsupported_path`, token `unix_domain` or `vsock` |
| UDP accept, or a listener whose accept protocol is UDP | `unsupported_path`, token `udp_peer_attribution` |
| Accept `mechanism` or `path` `io_uring` | `unsupported_path`, token `io_uring_accept` |
| Local address `127.0.0.11` or `::ffff:127.0.0.11` | `unsupported_path`, token `docker_embedded_dns` |
| Cgroup id `0` or empty | `unattributable_cgroup` |
| Image digests absent and image binding not required | Partial `image_digest_binding_not_in_evidence`. Hold may still occur on the executable digest |
| Image binding required and a digest is absent | `integrity_unknown` |
| Iface omitted | Partial `iface_unnamed`. The program does not invent `lo` |
| Every result | Partial `full_iface_attribution_not_present` |

`not_present` on every result names inbound packet drop, `cgroup_skb` ingress, a TC ingress classifier, connection isolation, live cgroup freeze, the live quarantine executor, identity-provider revoke, a full inbound tree walk, stranger-host proof, and an off-host durable ledger. Those names do not themselves withhold a hold that the rest of the contract allows. They record what this process did not do.

## 2. Health

A hold needs `loader_up`, `evidence_writable`, `enroll_readable`, `netns_readable`, and `trace_map_available` all true, and coverage exactly `seeing`.

`cannot_see`, a missing coverage, any other coverage token (`partial`, `bogus`, `SEEING`, `coverage_unknown`), or any of those flags false yields `health_or_evidence_unavailable`. Protection echo `coverage_unknown` yields the same reason even when coverage is `seeing`. `degraded` and `honest_idle` keep the rows below.

Coverage `degraded` or protection echo `degraded` yields `health_degraded`.

Coverage `honest_idle` together with an accept yields `health_evidence_contradiction`. P0b uses `honest_idle` when there is no inbound established connection and no unexpected listener. An accept in that coverage is a contradiction, not a grant.

Protection echo `quarantined` yields `already_quarantined`. This program does not write that state.

## 3. Freshness

Rule id: `FRESHNESS_WINDOW_NOT_SET_EMIT_UNKNOWN`.

The shared catalog leaves the freshness window `NOT_SET` and reserves `CURRENT`, `HISTORICAL`, and `STALE`. Every result here sets `freshness` to `UNKNOWN`.

The caller may pass `freshness_window_ms` and `attested_at_ms`. That pair is `identity_attestation`:

| Attestation | Meaning |
| --- | --- |
| `INSIDE_CALLER_WINDOW` | Both numbers are finite, the stamp is not in the future, and the age is within the caller window |
| `OUTSIDE_CALLER_WINDOW` | The stamp is older than the caller window. Reason `stale_identity` |
| `WINDOW_ABSENT` | The window or the stamp is missing, or the stamp is in the future. Reason `identity_unknown` |

The DaemonSet heartbeat age of 60 seconds is not this window. This program does not read a heartbeat file.
