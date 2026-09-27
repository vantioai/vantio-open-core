# E2 — Delegated authority

Audience: INTERNAL_RESTRICTED

Status of every object in this file: `PLANNED`. Evidence tier `UNSET`. Customer validation `UNSET`. `schema_status` `unstable-pre-1.0`.

A delegation grants exercise. It does not transfer the E1 title. Phantom Engine remains the component that can attach a narrower or wider envelope on the enrolled host, and only after E3 approval and host verification.

Invariant 9 in the reference-monitor doctrine is Roadmap: no cross-agent delegation object exists, and no delegation may exceed the delegator's authority. Invariant 2 is Partial: a child must not receive more authority than its parent without an independently authorized delegation, and no first-class child-agent object exists. E2 specifies the grant those invariants require. Specifying it does not make either invariant Present.

## 1. Grant

A grant is one record with these fields. Names are planning names. They are not a wire schema and not a database.

| Field | Rule |
| --- | --- |
| `grant_id` | Opaque id minted with the record |
| `delegator` | A customer identity that already holds the authority being granted |
| `delegate` | A customer identity, or a workload identity when the domain is workload. Security and recovery delegates are customer people or customer-held roles, not the workload |
| `domain` | One of `workload`, `security`, `recovery` |
| `scope` | A subset of the delegator's current envelope: hosts, paths, destinations, spend or size caps, and the actions listed in the grant |
| `purpose` | Short customer reason. Not a prompt and not a payload |
| `not_before` | Start time. Required |
| `not_after` | Expiry. Required. Open-ended grants are outside this plan |
| `redelegation` | `forbidden` under the EG-D1 default |
| `approval_class` | The E3 class that authorized this grant |
| `rollback_target` | The envelope version that becomes the ceiling when the grant ends |
| `state` | One of the states in section 3 |

Numeric lifetimes are `NOT_SET` (EG-D7). The field is required. The duration is not chosen in this packet.

Identity values are opaque customer-held identifiers. This plan does not select an identity provider.

## 2. Subset rule

EG-E2-1. At the moment the grant is approved, every host, path, destination, cap, and action in `scope` is already inside the delegator's envelope.

A grant that adds a destination, raises a cap, removes a path constraint, or adds a domain the delegator does not hold is not a delegation. It is an attempt to widen authority. Widening uses approval class `WIDEN` and still cannot exceed the customer root's envelope or the Phantom Engine boundary on hosts the customer has enrolled.

A workload cannot be the delegator of `security` or `recovery`. A workload cannot be the delegate of `security` or `recovery`.

Spawning a process, a container, or another agent does not create a grant. Fork inheritance of an already enrolled cgroup, which the doctrine describes as a present hook, shares the parent's current egress scope. It is not a new delegation and it is not permission to exceed that scope.

## 3. States

| State | Who may assert it | Meaning |
| --- | --- | --- |
| `PROPOSED` | Enterprise record | The delegator has asked. The approval class is not yet satisfied |
| `APPROVED` | Enterprise record | The E3 class is satisfied. The host has not reported attachment |
| `ACTIVE` | Host report only | Phantom Engine on the customer host reports a matching envelope version |
| `EXPIRED` | Time plus a host check | `not_after` has passed. Expanded authority must be gone |
| `REVOKED` | Customer root or the issuing delegator | Exercise has returned within E1. Title has not moved |
| `REFUSED` | Host report | Phantom Engine refused to attach. The Enterprise record stays a proposal outcome |

EG-E2-6. Enterprise displays `APPROVED` as approved. It displays `ACTIVE` only when quoting the host report. An Enterprise writer does not set `ACTIVE` because an approver clicked through.

When the grant is `EXPIRED` or `REVOKED`, the host envelope returns to a set that is inside `rollback_target`. The doctrine's contradiction "an exception expired, but the expanded authority remains" is Roadmap. EG-E2-8 requires that contradiction to be detected and refuses to mark the property passed. Status: `UNSATISFIED`.

## 4. Redelegation

EG-D1 default: `redelegation` is `forbidden`.

A delegate with a forbidden redelegation flag who issues a further grant produces `REFUSED` at proposal time. The safe default stands until a Founder allows a later grant that is still a subset of the delegate's remaining scope and still carries its own expiry. This packet does not open that later grant.

## 5. Independence

The delegator and the second approver on a `WIDEN` grant are distinct customer identities. The same person approving twice does not satisfy the class. The doctrine's invariant 9 test uses the same rule, by parity with dual-control self-approval rejection. E2 adopts the rule for customer grants. It does not claim the dual-control executor is live. The reference-monitor file says dangerous executors are unwired, and the separate dual-control spec it cites was not in the tree that was read.

A workload identity is never the independent approver of a grant that affects that workload.

## 6. Revocation of a grant

| Grant domain | Who may revoke | Approval class |
| --- | --- | --- |
| `workload` | The issuing delegator, inside the remaining grant, or the customer root | `NARROW` for the issuing delegator; `ROOT` always sufficient |
| `security` | Customer root | `ROOT` |
| `recovery` | Customer root | `ROOT` |

Revocation removes exercise. The customer root still holds title. Revocation does not appoint Vantio as owner, witness-of-record, or recovery party.

A delegate cannot revoke the root, cannot remove the recovery party, and cannot revoke Vantio's witness role. Those are E1 root acts.

## 7. What a grant must leave in place

Every grant, including a recovery-domain grant, leaves these customer-root powers intact:

- freeze
- revoke of that same grant
- recover within the E3 ceiling
- export, hash, rollback, and uninstall
- removal of Vantio's witness role

A grant field that hands any of those powers exclusively to Vantio is not a valid grant. The proposal ends in `REFUSED`.

## 8. Requirement index

| Id | Statement | Status |
| --- | --- | --- |
| EG-E2-1 | Scope is a subset of the delegator's envelope at approval time | `PLANNED` |
| EG-E2-2 | `not_before` and `not_after` are required. Duration numbers stay `NOT_SET` | `PLANNED` |
| EG-E2-3 | Workloads do not hold or receive `security` or `recovery` | `PLANNED` |
| EG-E2-4 | Process spawn does not mint a grant | `PLANNED` |
| EG-E2-5 | Redelegation is `forbidden` until EG-D1 is decided otherwise | `PLANNED` |
| EG-E2-6 | `ACTIVE` is a host report. `APPROVED` is not attachment | `PLANNED` |
| EG-E2-7 | Revocation returns exercise and leaves title with the customer root | `PLANNED` |
| EG-E2-8 | Expiry and revocation leave no expanded authority. Property required, current sources do not show it passed | `UNSATISFIED` |

## 9. Honesty against today's hooks

| Today's hook | E2 reading |
| --- | --- |
| Trace id inherited across `sched_process_fork` | Correlation. Not a delegation record |
| Enrolled cgroup children share scoped egress | Parent envelope continues. Not a wider grant |
| No Identity, Delegation, or Duration objects for agent-to-agent grants | The gap E2 is written against. Objects in this file are not those runtime objects |
| Zone-isolation notes in the doctrine | Company-host research. Not a customer delegation language |
