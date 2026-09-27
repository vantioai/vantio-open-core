# Shared health runtime architecture

Audience: INTERNAL_RESTRICTED

Producer classification: `SHARED_HEALTH_RUNTIME_READY_FOR_COUNCIL`

Normative lists: `packages/shared-health-runtime/contract.json`.

## 1. Record

`record_type` is `SHARED_HEALTH_RUNTIME_STATE`. Schema status is `0.1.0-unstable`. `stable_schema` is false.

The twelve states are:

`HEALTHY_ENFORCING`, `HEALTHY_OBSERVING`, `INTENTIONALLY_DISABLED`, `UNSUPPORTED`, `PARTIAL_COVERAGE`, `DEGRADED`, `STALE`, `DISCONNECTED`, `EVIDENCE_UNAVAILABLE`, `ENFORCEMENT_UNKNOWN`, `ROLLBACK_INCOMPLETE`, `UNINSTALL_INCOMPLETE`.

Every sealed record includes: `component`, `scope`, `evidence_source`, `timestamp`, `freshness`, `source_version`, `producer`, `independent_verification_status`, `limitation`, `failure_classification`, `last_known_good`, `safe_corrective_action`, `recovery_verification`.

`freshness` is `UNKNOWN`. `independent_verification_status` is `NOT_INDEPENDENTLY_VERIFIED`. `recovery_verification` is `NOT_VERIFIED`. `last_known_good` is null when the caller did not supply a non-optimistic prior record.

`audit.green`, `audit.proved`, `audit.live_phantom_enforcement_changed`, and `audit.this_runtime_executed` are false.

## 2. How a state is chosen

The producer reads caller evidence in memory. It does not open a socket, spawn a process, or read `/run/vantio/heartbeat`.

| Input that qualifies | State |
| --- | --- |
| One protection evaluation `protected`, with an allowed evidence class, platform status, and scope | `HEALTHY_ENFORCING` |
| One protection evaluation `observing`, with the same gates | `HEALTHY_OBSERVING` |
| Explicit lifecycle `intentionally_disabled` | `INTENTIONALLY_DISABLED` |
| Explicit lifecycle `unsupported` | `UNSUPPORTED` |
| Explicit lifecycle `partial_coverage` and at least one named gap | `PARTIAL_COVERAGE` |
| Protection evaluation `degraded` or `quarantined` | `DEGRADED` |
| Protection evaluation `protection_stale` or `policy_stale` | `STALE` |
| Explicit lifecycle `disconnected` | `DISCONNECTED` |
| No usable evidence, or a lifecycle withheld for a missing timestamp | `EVIDENCE_UNAVAILABLE` |
| Process up, HTTP 200–399, loader liveness, Optics display, SDK action, verifier result, ledger action, `not_enrolled`, `coverage_unknown`, or `recovery_required` | `ENFORCEMENT_UNKNOWN` |
| Explicit lifecycle `rollback_incomplete` | `ROLLBACK_INCOMPLETE` |
| Explicit lifecycle `uninstall_incomplete` | `UNINSTALL_INCOMPLETE` |

A requested state never upgrades the derived state. Process up and HTTP status do not select a healthy token. When those signals sit beside a qualified protection fact, the token can still be healthy and `audit.http_status_ignored` or `audit.process_up_ignored` is true.

`not_enrolled` is not `INTENTIONALLY_DISABLED`. `recovery_required` is not `ROLLBACK_INCOMPLETE` or `UNINSTALL_INCOMPLETE`. A control-plane heartbeat fact is not `DISCONNECTED`. `quarantined` is `DEGRADED` and does not add a thirteenth state.

## 3. Healthy-token gates

`HEALTHY_ENFORCING` and `HEALTHY_OBSERVING` require all of the following:

- `fact_kind` `PROTECTION_EVALUATION` on subject `LOADER` or `COVERAGE`
- `evidence_class` `OBSERVED_FROM_REPOSITORY_EVIDENCE` or `EXECUTED_IN_THIS_REMEDIATION`
- `platform_status` `VERIFIED_ON_REFERENCE_HOST` or `TESTED_LOCAL`
- `scope` `REPOSITORY_ONLY`, `WSL2_PRIVILEGED`, `KIND_LOCAL`, or `REFERENCE_HOST`
- a caller timestamp, producer, and source version
- failure classification equal to the token meaning: `fail_closed` for enforcing, `fail_open` for observing

`MANAGED_CLOUD` and `STRANGER_HOST` block the healthy token. `KIND_LOCAL` is not rewritten to `MANAGED_CLOUD`. `internally_proven` is not `STRANGER_HOST`.

`NOT_EXECUTED_IN_THIS_PASS`, `NOT_INDEPENDENTLY_VERIFIED`, `UNVERIFIED`, `DOCUMENTED_REQUIREMENT`, and `TARGET_DESIGN` block the healthy token.

The caller cannot set independent verification to a council pass. This runtime does not mint one. A caller `EXECUTED_IN_THIS_REMEDIATION` value is stored as a claim. `audit.this_runtime_executed` stays false, so the claim is not a measurement made here.

## 4. Failure classification

| State | Classification | Basis |
| --- | --- | --- |
| `HEALTHY_ENFORCING` | `fail_closed` | `TOKEN_MEANING` |
| `HEALTHY_OBSERVING` | `fail_open` | `TOKEN_MEANING` |
| `INTENTIONALLY_DISABLED` | `unsupported` | `TOKEN_MEANING` |
| `UNSUPPORTED` | `unsupported` | `TOKEN_MEANING` |
| Every other state | `unsupported` unless the caller sets `failure_mode_evidenced` | `NOT_EVIDENCED` or `CALLER_EVIDENCED` |

Token meaning is not a latch measured by this process. The limitation says so.

## 5. Collisions kept from the bound catalog

- State `STALE` is not freshness `STALE`. Freshness stays `UNKNOWN`. `CURRENT` and `HISTORICAL` are not emitted.
- Application `SUCCESS` and HTTP 200–399 are not enforcement health.
- Optics `OBSERVED` and Optics `SUCCESS` are not `protected`.
- Verifier `PASS` is not a healthy token. `OPTIONAL_COMPONENT_ABSENT` is not `PASS`.
- Verifier `BLOCKED` and ledger `BLOCKED` stay different facts. Neither one becomes `HEALTHY_ENFORCING`.
- Ledger `OBSERVED` is not `protected`.
- A coverage percentage is rejected. Partial coverage is a list of named gaps.
- Loader heartbeat age is not freshness and is not the control-plane interval.

## 6. Components

Runtime components are the six catalog subjects plus `OPTICS` and `SDK`. Those two names are not catalog subjects. `UNSPECIFIED` is used only on `EVIDENCE_UNAVAILABLE` and `ENFORCEMENT_UNKNOWN` when no component was supplied.

## 7. Consumption

`consume` accepts a sealed record only when the evidence fields and the audit flags match this contract. It returns `green: false` for both accepted and refused records. A healthy presentation that is missing fields, cites HTTP or process up, uses a stranger-host or managed-cloud scope, or carries a proved bit or a council pass is reported as `ENFORCEMENT_UNKNOWN` and is not accepted. A non-healthy presentation with missing evidence fields is reported as `EVIDENCE_UNAVAILABLE`.

`consumeFact` is `produce` with one catalog fact.

## 8. Council questions

These are decisions in this implementation, left for the council to accept or send back:

- Healthy tokens are emittable from caller-supplied protection facts while `green` stays false. A later force can refuse the token until an execution record exists.
- `unsupported` is the failure classification when the caller did not evidence `fail_open` or `fail_closed`.
- `quarantined` maps to `DEGRADED` rather than a new state.
- `recovery_required` maps to `ENFORCEMENT_UNKNOWN` until rollback or uninstall is an explicit lifecycle.
- Repository observation can carry a healthy token. Independent verification stays `NOT_INDEPENDENTLY_VERIFIED`.
