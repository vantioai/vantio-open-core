# Stranger-host gate

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INTERNAL_RESTRICTED`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Define the gate that would have to be passed before an external claim uses the tier `STRANGER_HOST_PROVED`. The gate is a proof requirement. It is not a procedure for obtaining a host.

## Definition

From `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` and the internal roadmap: the same named check passed on a host that is not the producer's development environment.

That result does not establish `CUSTOMER_VALIDATED`.

Current assignment: none. Tier now: unset.

## Checklist for a future record

| Item | Value |
| --- | --- |
| Check name | `NOT_FILLED` |
| Producer environment the check was first run on | `NOT_SET` |
| Second host class | `NOT_SET` |
| Operator distinct from the producer | `NOT_SET` |
| Date | `NOT_SET` |
| Package versions | `NOT_SET` |
| Artifact location | `NOT_SET` |
| Result | `UNSET` |
| Customer workload | Out of scope for this tier |

## Prohibited contents

- Access steps, credentials, and account identifiers
- Exploit material or bypass demonstrations used to reach a host
- A customer name
- Instructions for enrolling or attacking infrastructure

## Relationship to other tiers

| After this gate | Still required before an external claim that needs it |
| --- | --- |
| `STRANGER_HOST_PROVED` for the named check | An independent verifier for `PROVED_EXTERNAL` |
| Either of the above | A customer workload and window for `CUSTOMER_VALIDATED` |

Repository tests on a developer or CI runner do not satisfy this gate. See [08-PROOF-TAXONOMY.md](08-PROOF-TAXONOMY.md).
