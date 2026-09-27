# Enterprise E1–E3 architecture notes for council

Audience: INTERNAL_RESTRICTED

These notes are the architecture record for the internal evaluator. They are not a council verdict. Seats are in `04-PENDING-COUNCIL.md`.

## 1. Placement

The evaluator lives in `internal/enterprise-governance/`. Callers pass plain objects and receive a result. Nothing in the module opens a socket, reads a host, or imports a package under `packages/`.

Phantom Engine remains the enforcement plane. An enroll intent stores `enrolled: false`, `protected: false`, and `enforced: false`, and names the mechanism `PHANTOM_ENGINE_ON_CUSTOMER_HOST` without performing it. A retire intent keeps the "record says retired, process may still be active" contradiction visible. This module does not clear it.

## 2. Parties

An identity is an opaque string the caller already holds, plus a caller-asserted kind: `customer`, `workload`, or `vantio`. Accepting that pair records a handle. It does not create an external identity, a credential, or a proof.

| Rule | Evaluator behavior |
| --- | --- |
| Vantio is not in the root set | Kind `vantio` cannot found the root, join the owner set, or be the recovery party. Relabeling the same id as `customer` is refused |
| Workload is not title | Kind `workload` cannot found the root or receive `security` or `recovery` |
| Roles are not proof | `role`, `roles`, `role_labels`, and `claimed_role` do not fill a seat |
| Consensus is not approval | `agent_consensus`, `consensus`, `votes`, and `agent_votes` do not fill a seat |
| Distinct ids are not a human proof | The same id twice is rejected for `WIDEN`. Two different strings are not checked as the same person. `identity_authenticated` stays false |

`recordRecognizedCustomer` lets the root record that an already accepted customer handle may sit a `WIDEN` seat. Recognition is not membership in the root set and does not mint a grant.

## 3. Title and exercise

Founding stores `title_holder: customer_root` and the reserved powers `freeze`, `revoke_grant`, `recover`, `export`, `hash`, `rollback`, `uninstall`, and `remove_witness`. Grants do not delete that list. A grant field that hands any of those powers exclusively to Vantio is refused.

The founding call also stores an authority ceiling and an initial policy. The policy must be a subset of the ceiling. Later `WIDEN` may move policy up to the ceiling and not past it. The plan does not define a ceremony for raising the ceiling, so this evaluator refuses that change instead of inventing one.

## 4. Envelope subset

A child envelope is inside a parent when:

- hosts, destinations, actions, and domains are subsets
- every parent path constraint is still present
- a numeric cap is not raised, and a cap is not removed

Adding a path constraint or lowering a cap is a narrow. Adding a destination, raising a cap, dropping a path constraint, or adding a domain is a widen. A grant that does any of those against the current policy is refused as `NOT_A_DELEGATION_WIDENS`. `WIDEN` of policy must be a pure widen inside the ceiling, with `not_after` set. The duration number is `NOT_SET`. The caller supplies the timestamps. The module does not invent a product limit.

## 5. Grants, spawn, and expiry

A new grant requires class `WIDEN`, two distinct customer identities inside the recognized set, and a delegate who is not one of those two. The delegator must be in the root set. Any other delegator is `REDELEGATION_FORBIDDEN` while EG-D1 stays unresolved. A `redelegation: allowed` flag is refused.

`noteSpawn` does not insert a grant. A child envelope must be a subset of the grant scope while the window is open, and a subset of `rollback_target` after the clock passes `not_after` or after revocation. A missing parent does not mint a grant.

`noteClock` applies `not_before` and `not_after` on the record. Before the window, exercise is `NOT_YET`. After `not_after`, exercise is `ENDED` and further record-layer use of the expanded scope stops. The grant state is not set to `EXPIRED`, and `host_expanded_authority_cleared` stays `UNSATISFIED`. That is EG-E2-8: the record stops handing out the expansion; the host maps are not observed.

An open policy widen is tightened back toward its rollback on the same clock, including after a later narrow, by intersection of authority. The tighten step does not add a destination, host, action, or domain, does not drop a path constraint, and does not raise a cap. Host clearance stays `UNSATISFIED`.

## 6. Approval classes

| Class | Seats | Notes |
| --- | --- | --- |
| `INSPECT` | One customer root, or one customer inside an open read grant | A policy body on the call is refused |
| `NARROW` | The root, or one customer holding an open security grant | The change must be a strict subset. A delegate cannot change domains or edit outside the grant |
| `WIDEN` | Exactly two distinct customer identities. EG-D2 default | A witness does not count. Three seats are refused. The same id twice is rejected |
| `ROOT` | A member of the root set. EG-D9 default is one | Owner set, recovery party, witness removal, enroll intent, retire intent, security and recovery revocation |
| `RECOVERY` | The recovery party or the root | Completes with no Vantio seat. Modes are `last-known`, `observe-only`, and `stay-quarantined` |
| Missing class | None | `REFUSED` / `MISSING_CLASS` |
| Rejected acts | None | `REJECTED`. No approval record is stored |

A recorded freeze uses `RECOVERY` and then blocks later grants and policy widens in this store. Narrowing still works. `host_freeze_performed` stays false. EG-E3-8 stays `HOST_UNSATISFIED`.

`stay-quarantined` does not thaw. A proposed envelope outside the pre-containment snapshot is `WIDER_THAN_CEILING`. A fourth mode is rejected. That comparison is the record rule for EG-E3-7. It does not clear the Phantom Engine residual, so the requirement stays `RECORD_LAYER_ONLY_HOST_UNSATISFIED`.

## 7. ACTIVE is a quote

The enterprise grant state is never assigned `ACTIVE`. `quoteHostReport` accepts `source: "host_report"` only. `enterprise_writer`, `approver_click`, `console`, `dry_run`, `billing`, and `support` are rejected. The quote is stored beside the grant. `displayGrant` reports `display_active` only from that quote, with `verified_on_host: false` and `host_contacted: false`. A version mismatch does not store the quote.

This is a caller-supplied quote inside a unit test or a later adapter. It is not evidence that a host was reached.

## 8. Store outage

`setRecordStoreAvailable(false)` blocks widening writes, including new grants and new `ACTIVE` quotes. A customer root can still record a freeze on the customer-held object; after the flag is turned back on, the freeze still blocks widening. `recover` and `leaveFromCustomerHeldMaterial` read the material argument and do not require the hosted flag. A `vantio_only` holder is rejected. No bytes of prompts, completions, or credentials are stored. Those keys are refused.

## 9. What a passing test does not prove

| Id | This branch | Still unsatisfied |
| --- | --- | --- |
| EG-E2-8 | Record layer stops expanded exercise after the clock or revocation | Host maps were not read |
| EG-E3-7 | Wider-than-snapshot recovery is rejected in the record | Phantom Engine ceiling check was not run |
| EG-E3-8 | Freeze is a customer record | No one-shot freeze on a host Vantio does not operate |
| EG-SUB-6 | Not implemented | No customer-owned on-host channel |
| EG-SP-1 through EG-SP-5 | Not run | Need a host this process does not operate, with Vantio absent |

Company-host dogfood is not the customer model (EG-D8). This workspace did not run those host tests, and a unit suite must not be described as if it had.
