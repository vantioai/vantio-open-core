# Pending council — Enterprise E1–E3 internal

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL`

Revision handoff: `ENTERPRISE_E1_E3_INTERNAL_REVISION_READY_FOR_COUNCIL`

That classification is the handoff. It is not a verdict. The producer `bc-c9b05a34-636c-589b-987b-4ea94e4f8c4c` does not fill the verdict column. A later revision on the same draft pull request closed three record-layer holds (`not_before`, sticky `ENDED`, and a later `NARROW` bounding existing grants). A further revision, after council `bc-fb458789-7599-5abb-a10f-ccc17f25ead3` returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on `db70e93bca42d7d5be56b2afaed4d1c95a24cf24`, closed deferred-widen composition holds A–E. Council `bc-9e4306a5-2874-5ae1-ba2e-c6aadfd1ba5b` then returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on `73f291b009f4b0d223c5003385f38973a3a5e8b1` and reopened holds A and B. A further revision on the same draft closed those two holds without reopening C–E or the isolated holds. Council `bc-3cc20d59-8923-5424-b1ba-ac17db02854a` then returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on `34a1d2ad1007e573cc1fac137f334b2acb5c3a33`: a clock restored a stored widen target when the live cap was already above the ceiling recorded for that widen. A further revision on the same draft keeps that live cap (spend 85, size 75, and spend 75 through a March clock that drops expired `d2`). None of these revisions fills the verdict column. Host proofs stay open.

The plan council in `docs/planning/enterprise-governance/06-INDEPENDENT-COUNCIL.md` is a different review and is still pending. This file does not close it.

## Identity to be filled by the council

| Item | Value |
| --- | --- |
| Council agent | unset |
| Council URL | unset |
| Model | unset |
| Reviewed tip | unset |
| Reviewed at (UTC) | unset |
| Verdict | unset |

## Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Record layer versus host proof, including EG-E2-8, EG-E3-7, EG-E3-8, EG-SUB-6, and EG-SP-1 through EG-SP-5 | `PENDING_INDEPENDENT_COUNCIL` |
| 2 | E1 title, root set, and host intent versus enrollment | `PENDING_INDEPENDENT_COUNCIL` |
| 3 | E2 subset, expiry, redelegation, and spawn | `PENDING_INDEPENDENT_COUNCIL` |
| 4 | E3 classes and rejected acts | `PENDING_INDEPENDENT_COUNCIL` |
| 5 | Self-approval, agent consensus, and role-as-proof | `PENDING_INDEPENDENT_COUNCIL` |
| 6 | Customer-held freeze, revoke, and recover versus a Vantio-only path | `PENDING_INDEPENDENT_COUNCIL` |
| 7 | Store outage does not widen | `PENDING_INDEPENDENT_COUNCIL` |
| 8 | Prohibited fields and the absence of credentials | `PENDING_INDEPENDENT_COUNCIL` |
| 9 | No package change, no second enforcement plane, no identity provider | `PENDING_INDEPENDENT_COUNCIL` |
| 10 | EG-D1 through EG-D10 left unresolved, including EG-D5 and EG-D6 | `PENDING_INDEPENDENT_COUNCIL` |

## What the council reviews

- `internal/enterprise-governance/` and `tests/enterprise-e1-e3/` against the plan packet at merge `8eb353a94c08c1adaaa36d36e2536ee5619e9eb6`, which is an ancestor of starting commit `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.
- The architecture notes in `02-ARCHITECTURE.md`.
- Absence of diffs under `packages/`, `extensions/`, `.github/`, `docs/governance/`, and `docs/planning/enterprise-governance/`.
- The producer did not write a pass in the verdict column.
