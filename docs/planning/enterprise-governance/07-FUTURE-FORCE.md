# Future force template — Enterprise E1–E3 implementation

```
NOT AUTHORIZED
DRAFT FOR FOUNDER REVIEW
DO NOT EXECUTE
```

This file is a copy-ready draft. It does not open an implementation. It does not authorize a branch, a Phantom Engine change, or a package change. A Founder copies it into a later force and fills the placeholders before any agent runs it.

Producer of this draft: planning agent `bc-53037043-9d63-5b25-9945-484d22d0eaa7`. Classification of the planning packet: `ENTERPRISE_GOVERNANCE_E1_E3_PLAN_READY_FOR_COUNCIL`. That classification is not permission to run this template.

---

FOUNDER FORCE — ENTERPRISE E1–E3 IMPLEMENTATION (NOT AUTHORIZED)

## Locked starting state

Planning packet:

`docs/planning/enterprise-governance/`

Planning tip the Founder names:

`{{PLANNING_TIP_SHA}}`

Council classification required before this force runs:

`ENTERPRISE_GOVERNANCE_E1_E3_PLAN_COUNCIL_PASSED` on that exact tip, written by an agent other than `bc-53037043-9d63-5b25-9945-484d22d0eaa7`.

Phantom Engine commit the Founder names:

`{{PHANTOM_ENGINE_SHA}}`

On mismatch with the planning packet's cited commit, stop unless the Founder records the drift. Stop token: `ENTERPRISE_E1_E3_BLOCKED_INPUT_DRIFT`.

## Repository fence

Implementation of host activation, freeze, recover, and enrollment belongs in `vantio-phantom-engine` and on a host the customer operates.

This open-core repository stays docs-only for that work unless the Founder names a different repository and a path outside `packages/` and `extensions/`. Optics packages, `@vantio/cli` `0.3.24`, and the account-free Observe tier stay unchanged.

Do not wire `phantom_deny_breakglass_off`. Do not wire the quarantine executor unless the Founder names that executor in a separate force. Do not select Spanner, a WORM product, or a proof system unless EG-D6 is explicitly resolved in the authorizing force.

## Decisions

EG-D5 and EG-D6 must be confirmed or explicitly left on their defaults in the authorizing force. EG-D1 through EG-D4 and EG-D7 through EG-D10 may remain on the defaults in `05-UNRESOLVED-FOUNDER-DECISIONS.md`.

## Tests that would count later

EG-SP-1 through EG-SP-5 in `04-SUBORDINATION-AND-CUSTOMER-SUFFICIENCY.md`. A company-host rehearsal does not satisfy them. Passing unit tests on a loader does not satisfy them.

## Still closed even after authorization

- Public claims that the reference monitor is Present.
- Certifications.
- A Vantio-only freeze, revoke, or recover path.
- An Optics account requirement.
- Promotion of this template by the agent that finds it. The Founder authorizes a later force in a separate instruction.
