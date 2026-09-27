# Subordination and customer sufficiency

Audience: INTERNAL_RESTRICTED

This file binds E1, E2, and E3 to the Phantom Engine authority boundary, and it binds freeze, revoke, and recover to a customer-controlled party.

Requirements here are `PLANNED` unless a row says `UNSATISFIED`. Evidence tier `UNSET`. Customer validation `UNSET`. No row is a passed test.

## 1. Subordination

Enterprise is governance on top of Phantom Engine. The boundary that can attach enforcement is Phantom Engine on enrolled Linux the customer owns.

| Id | Rule | Status |
| --- | --- | --- |
| EG-SUB-1 | An Enterprise approval is a proposal until the host reports a matching active version. A Phantom Engine refusal leaves the proposal `REFUSED` | `PLANNED` |
| EG-SUB-2 | Enterprise does not mark a host protected, enrolled, or enforced. Protection state comes from the on-host reporter | `PLANNED` |
| EG-SUB-3 | If the Enterprise record store is unavailable, last-known host enforcement continues. The outage is not a reason to widen the envelope | `PLANNED` |
| EG-SUB-4 | This open-core repository does not gain a second enforcement engine, a host loader, or an enroll command | `PLANNED` |
| EG-SUB-5 | Free Optics stays observe-only and account-free. Governance records are not a precondition for local observation | `PLANNED` |
| EG-SUB-6 | The customer-owned on-host channel presents an approved record to Phantom Engine. The hosted store is not that channel | `UNSATISFIED` |

The reference-monitor doctrine puts the management experience outside the trusted computing base: consoles, billing, and convenience UX may degrade, and the boundary must not silently disappear. EG-SUB-3 is that rule applied to Enterprise.

## 2. Customer sufficiency

For freeze, revoke, and recover of customer authority:

A customer-controlled party can complete the action while Vantio contributes no credential, no approval, and no hosted service.

| Action | Sufficient party | Vantio's allowed role under EG-D3 |
| --- | --- | --- |
| Freeze | Customer recovery party, or the customer root | Optional witness. The action completes if the witness is absent |
| Revoke a grant, the witness role, or exercise under a grant | Customer root, or the issuing delegator where E2 allows | Optional witness on `ROOT`. Not a required signer |
| Recover | Customer recovery party, or the customer root, inside the E3 ceiling | Optional witness. The action completes if the witness is absent |

Vantio is not a sufficient party for any row. A design where Vantio is the only party that can freeze, revoke, or recover is class `REJECTED`.

Verify, export, and leave sit in the same Phantom Engine invariant (invariant 10). E1 keeps them customer-sufficient so this plan does not narrow that invariant while it specifies freeze, revoke, and recover.

## 3. Tests

These tests are specified. They are not run. Each status is `UNSATISFIED`. A Phantom-Box rehearsal does not satisfy them. The doctrine already says a rehearsal on the company host is not the stranger-host leave test.

| Id | Test | Pass condition |
| --- | --- | --- |
| EG-SP-1 | Freeze | On a host Vantio does not operate, with the Vantio control plane unreachable and no Vantio credential on the host, the customer recovery party freezes the named scope |
| EG-SP-2 | Revoke | With every Vantio credential absent, the customer root revokes a delegate and revokes Vantio's witness role. Title remains with the root |
| EG-SP-3 | Recover | With Vantio absent, recover ends in `last-known`, `observe-only`, or `stay-quarantined`, and the restored envelope is a subset of the pre-containment snapshot |
| EG-SP-4 | Vantio-only attempt | A Vantio-only credential attempting freeze, revoke, or recover is refused. Host authority is unchanged |
| EG-SP-5 | Leave | Export, hash, rollback, and uninstall complete with Vantio absent. The customer keeps the exported evidence |

EG-SP-1 aligns with the doctrine residual `independent_freeze_not_present`. Naming the test does not clear the residual.

## 4. Activation sequence

Target sequence for a proposal that is allowed to affect the host. This sequence is `PLANNED`. It is not implemented.

1. The customer parties named by the E3 class agree. Enterprise stores an approval record (`03-E3-APPROVAL-CLASSES.md` section 6).
2. A customer-owned channel on the host presents that record to Phantom Engine.
3. Phantom Engine checks attribution, version, subset of the customer envelope, presence of expiry where the class requires it, presence of a rollback target where the class requires it, and the presence of a customer party who can still freeze, revoke, and recover if Vantio is removed.
4. Phantom Engine attaches a matching envelope or refuses.
5. The host protection report is the source for `ACTIVE` or `REFUSED`. Enterprise stores that report beside the proposal.

Step 2 is the customer-owned channel the doctrine calls Roadmap (propose, approve, Phantom Engine verifies both, customer-owned channel activates). This plan requires the channel and records it `UNSATISFIED` as EG-SUB-6.

If step 2 cannot reach a live proposer because the hosted record is down, the host keeps last-known enforcement (EG-SUB-3). Local `RECOVERY` still runs from customer-held material on the host (EG-E3-3).

## 5. Control-plane compromise

Layer 9 of the doctrine: a security product must not become the easiest universal control point for an attacker. Applied here:

| Condition | Required outcome | Status |
| --- | --- | --- |
| Hosted Enterprise store is unavailable | Host keeps last-known enforcement. Local recovery still works | `PLANNED` rule, `UNSATISFIED` proof |
| Hosted store is untrustworthy | Host accepts customer-attributed proposals that Phantom Engine can verify. Unsigned loosening is `REJECTED` | `UNSATISFIED` |
| Vantio witness key is stolen | Witness cannot satisfy a class. Customer root removes the witness role at `ROOT` without that key | `PLANNED` rule, `UNSATISFIED` proof |
| Customer root is lost | The pre-named customer recovery party recovers title. Vantio does not appoint a replacement root | `PLANNED` |

## 6. What subordination forbids in this repository

- Changes under `packages/`, `extensions/`, `.github/workflows/`, or `docs/governance/`.
- A new CLI command that enrolls a host, loads a kernel program, freezes a workload, or recovers an envelope.
- Treating `@vantio/gate-mcp` dry-run as an approval class or as host activation.
- Editing the public product boundary to say Enterprise is the enforcement product.

The future-force template in `07-FUTURE-FORCE.md` stays `NOT AUTHORIZED`. Even after a Founder authorizes work, the first implementation home is the Phantom Engine customer host path, not an Optics package.
