# Proof taxonomy

Audience: INTERNAL_RESTRICTED

Document status: SKELETON

Future slot: `INVESTOR_UNDER_NDA`

Fill status: `NOT_FILLED`

Investor send: `NOT_CLEARED`

External publication: PROHIBITED

## Purpose

Name the evidence tiers this company already uses in internal architecture docs, and record that this room assigns none of them.

## Tiers

Defined for later use. Definitions below follow `docs/architecture/optics-foundation/09-IMPLEMENTATION-GATES.md` and `docs/internal/optics-best-in-class-roadmap.md`. This file does not retier any work.

| Tier | Meaning used in those docs | Assigned by this room |
| --- | --- | --- |
| `UNIT_PROVED` | The named check passed as a unit fixture. Not sufficient by itself for an external claim. | None |
| `INTEGRATION_PROVED` | The named check passed across the components the claim joins, such as Node and Python writing one store. | None |
| `STRANGER_HOST_PROVED` | The same check passed on a host that is not the producer's development environment. This does not establish customer validation. | None |
| `PROVED_EXTERNAL` | An independent verifier recorded the result. | None |
| `CUSTOMER_VALIDATED` | A customer workload and window. Separate from the tiers above. | None |

`INTERNAL_PROOF` appears in the internal roadmap as a requirement-status value. It is not an evidence tier. It must not be displayed as `CUSTOMER_VALIDATED`.

## What repository tests are

`docs/products/optics/KNOWN-LIMITATIONS.md` states that repository tests exercise CLI commands, the Node interceptor on supported clients, telemetry allowlists, and the Python observe hooks. They are unit and integration tests in this repo. They are not a customer deployment, not a stranger-host proof, and not a certificate.

This taxonomy agrees with that paragraph. It does not assign a tier to those tests.

## Producer documents

A council pass on an architecture or planning pack is a document result. `docs/architecture/optics-foundation/00-PROGRAM-BOUNDARY.md` states that the pack assigns none of the five tiers above. Passing a document gate is not one of those tiers.

## Sections still empty

| Section | Value |
| --- | --- |
| Mapping from each public claim to a tier | `NOT_FILLED`. See the ledger. All `UNSET`. |
| Artifact format for a future stranger-host record | `NOT_FILLED`. See [18-STRANGER-HOST-GATE.md](18-STRANGER-HOST-GATE.md). |
| External verifier identity | `NOT_SET` |
