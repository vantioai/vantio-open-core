# E3 — Approval classes

Audience: INTERNAL_RESTRICTED

Status of every class in this file: `PLANNED`. Evidence tier `UNSET`. Customer validation `UNSET`. `schema_status` `unstable-pre-1.0`.

An approval class answers who must agree before Enterprise may mark a proposal `APPROVED`. Agreement is not host attachment. Phantom Engine on the customer host attaches, refuses, or keeps last-known enforcement. Section 4 of `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md` is the activation sequence.

Dual-control hooks named in the reference-monitor doctrine are not these classes. That file says a two-of-two proof exists for a non-destructive test kind, and that the live executor for `phantom_deny_breakglass_off` is unwired. E3 does not wire it and does not number that test kind as a shipped class.

## 1. Classes

| Class | Token | Customer parties that satisfy it | Actions in class |
| --- | --- | --- | --- |
| Inspect | `INSPECT` | One customer identity inside a read grant | Read protection state, read grant records the party is allowed to see, export a copy of evidence the party can already read |
| Narrow | `NARROW` | One customer identity inside a security grant, or the customer root | Remove a destination, lower a spend or size cap, add a path constraint, revoke a workload grant the caller issued |
| Widen | `WIDEN` | Two distinct customer identities, both inside the customer root's envelope | Add authority inside the root envelope, issue a subset delegation, open a time-bounded exception |
| Root | `ROOT` | The customer root set, as sized by EG-D9 | Change the owner set, appoint or remove the recovery party, revoke a security or recovery grant, remove Vantio's witness role, record enroll intent or retire intent |
| Recovery | `RECOVERY` | The customer recovery party. The customer root can also exercise this class | Freeze, recover, export-and-leave |
| Rejected | `REJECTED` | No party, including Vantio | The acts in section 3 |

Vantio is not a satisfying party for any class. Under the EG-D3 default, Vantio may witness `WIDEN`, `ROOT`, and `RECOVERY`. The witness signature is not counted toward the customer quorum. For `RECOVERY`, the witness is optional in a stronger sense: the class still completes when Vantio is unreachable.

EG-D2 default for `WIDEN`: exactly two distinct customer identities. A larger quorum is a Founder decision. This plan does not pick a number above two.

EG-D10 default: a delegate with a security grant may use `NARROW` inside that grant. Widening stays `WIDEN`. Root-set changes stay `ROOT`.

## 2. Class rules

EG-E3-1. Every proposal carries one class. A missing class is `REFUSED`.

EG-E3-2. `WIDEN` uses two distinct customer identities. The same identity presented twice is `REFUSED`. The delegator of a new grant may be one of the two. The second identity is a different customer identity. A workload identity fills neither seat.

EG-E3-3. `RECOVERY` is sufficient when exercised by the customer recovery party with no Vantio credential, no Vantio approval, and no hosted Vantio service. The customer root may also exercise `RECOVERY`.

EG-E3-4. Narrowing is available at `NARROW` so a customer can reduce authority without waiting for a second person. Narrowing still cannot erase evidence, cannot present an unknown host as protected, and cannot appoint Vantio as the recovery party.

EG-E3-5. `ROOT` acts are unavailable to delegates, including delegates who hold `WIDEN`.

## 3. Rejected acts

These proposals are class `REJECTED`. No approval record can authorize them.

| Act | Why it is rejected |
| --- | --- |
| Vantio-only freeze of customer authority | Breaks customer sufficiency |
| Vantio-only revoke of the customer root, of a recovery party, or of a grant | Title would move to the vendor |
| Vantio-only recover, or a recover that reassigns the root to a party Vantio chooses | Same |
| Unsigned or unattributed loosening of host enforcement | Doctrine invariant 5, and layer 9's "no unsigned emergency loosening" |
| A console, billing event, or support action that attaches or detaches host enforcement | Management plane is outside the authority boundary |
| Workload self-approval | The workload does not hold security or recovery |
| Same-person dual control | Fails the distinct-identity rule |
| A restore wider than the pre-containment envelope | Breaks the recovery ceiling in section 4 |
| Counting an application-path dry-run as host activation | The doctrine separates Gate dry-run from Phantom Engine activation |
| A second enforcement engine inside Enterprise or inside this open-core repository | Enterprise stays subordinate |

Break-glass that turns protection off is not an E3 class. The doctrine names `phantom_deny_breakglass_off` and records its executor as unwired. If a later Founder force defines a customer break-glass, that force has to keep it customer-held, expiring, evidenced, and unable to become the only freeze, revoke, or recover path. This packet does not define that force as authorized.

## 4. Recovery ceiling

`RECOVERY` may end in exactly one of the modes the customer-pack notes already name:

| Mode | Result |
| --- | --- |
| `last-known` | Restore the last saved envelope. Path constraints that were on stay on |
| `observe-only` | Stop enforce actions. Leave the customer able to see. Do not treat observe as an authority expansion |
| `stay-quarantined` | Remain contained. This mode does not thaw |

EG-E3-7. The restored envelope is a subset of the envelope snapshotted before containment. Invariant 8 and prove row RM-08 (skip, residual `recovery_restoring_authority_ceiling_not_present`) mean this comparison is not present. The requirement stands. Its status in this packet is `UNSATISFIED`.

A fourth mode that returns a wider envelope, clears the customer root, or requires Vantio to complete is `REJECTED`.

## 5. Freeze

Freeze is a `RECOVERY` act. Its planning meaning is: stop further expansion of authority for the named scope, and contain that scope where the host can contain it.

The doctrine's residual `independent_freeze_not_present` and the unwired quarantine executor mean a customer one-shot freeze is not Present. EG-E3-3 specifies the class. It does not mark freeze Present. Status of the host action: `UNSATISFIED`.

Company-host freeze that depends on the named company operator is not this class. Decision EG-D8 keeps that path out of the customer model.

## 6. Approval record

When a class is satisfied, Enterprise stores:

| Field | Content |
| --- | --- |
| `approval_id` | Opaque id |
| `class` | One token from section 1, other than `REJECTED` |
| `subject` | Grant id, root change, enroll intent, retire intent, or recovery mode |
| `parties` | Customer identity ids that satisfied the class. Witness id, if any, in a separate field |
| `scope` | The proposed envelope or the recovery mode |
| `version` | Monotonic customer version of this decision |
| `rollback_target` | Required for `WIDEN` and for `RECOVERY` mode `last-known` |
| `not_after` | Required for exceptions and grants. `NOT_SET` as a number. Present as a field |
| `state` | `APPROVED`, then later updated from the host to `ACTIVE` or `REFUSED` |

The record does not contain prompts, completions, packet payloads, or credentials.

## 7. Requirement index

| Id | Statement | Status |
| --- | --- | --- |
| EG-E3-1 | Every proposal has one class. A missing class is refused | `PLANNED` |
| EG-E3-2 | `WIDEN` requires two distinct customer identities. Same-person approval is refused | `PLANNED` |
| EG-E3-3 | `RECOVERY` completes with the customer party and without Vantio | `PLANNED` |
| EG-E3-4 | `NARROW` cannot appoint Vantio, erase evidence, or mark a host protected | `PLANNED` |
| EG-E3-5 | Root-set, recovery-party, and Vantio-witness removal stay at `ROOT` | `PLANNED` |
| EG-E3-6 | Section 3 acts are `REJECTED` | `PLANNED` |
| EG-E3-7 | Recovery stays inside `last-known`, `observe-only`, and `stay-quarantined`, and does not restore a wider envelope | `UNSATISFIED` |
| EG-E3-8 | Customer one-shot freeze on a host Vantio does not operate | `UNSATISFIED` |

## 8. Relationship to Phantom Engine dual control

Use the doctrine's own limits:

- Dual-control kinds are named. Dangerous executors, including quarantine and `phantom_deny_breakglass_off`, are unwired.
- Two-of-two is tied, in that file, to a non-destructive test kind.
- A privileged operator on the host can still change maps. The customer approval class does not pretend to bind a root shell. That residual stays named.
- Self-approval rejection is a rule E3 requires of customer classes. It is not a claim that a live executor already enforces E3.

E3 is the customer governance layer those hooks do not yet implement.
