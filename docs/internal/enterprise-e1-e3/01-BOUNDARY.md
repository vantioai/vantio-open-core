# Enterprise E1–E3 internal boundary

Audience: INTERNAL_RESTRICTED

Producer classification: `ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL`

That classification means this branch is ready for a separate council. It is not a council verdict, not a merge, and not host proof.

## In scope

An in-memory evaluator that applies the merged plan's record rules:

- E1 title stays with the customer root. Vantio is not a member of the root set. Host enroll and retire are intent records. Policy approval is not host attachment.
- E2 grants are subsets, carry `not_before` and `not_after`, and do not transfer title. Redelegation stays forbidden. Spawn does not mint a grant. A child envelope wider than the permitted subset is refused.
- E3 classes are `INSPECT`, `NARROW`, `WIDEN`, `ROOT`, and `RECOVERY`. The rejected acts in the plan stay rejected. Same-person `WIDEN`, workload self-approval, and a grant recipient approving their own grant are refused as approval.
- Role labels and agent consensus do not satisfy a class. Opaque handles are not identity proof. No external identity and no credential is created.
- EG-D1 through EG-D10 stay unresolved. EG-D5 and EG-D6 stay on their defaults: this module does not activate a host, and it does not select a store product.

## Out of scope

- Live customer authority, a customer host, or a Phantom Engine process.
- Enrollment, kernel loading, egress drops, quarantine, and `phantom_deny_breakglass_off`.
- A second enforcement engine, a CLI command, or a change under `packages/`, `extensions/`, `.github/`, or `docs/governance/`.
- Edits to `docs/planning/enterprise-governance/`. The plan hashes stay those in `GOVERNANCE-MANIFEST.json`.
- CLI `0.3.24` and Python `3.1.0`.
- Certifications, a stable schema, Spanner, a WORM product, or a proof system.
- EG-SP-1 through EG-SP-5. Those tests need a host Vantio does not operate. They are not run.
- EG-E3-8 and EG-SUB-6. The record can state the rule. The host action and the on-host channel are not present.

## Schema

`schema_status` is `unstable-pre-1.0`. `schema_version` is `0`. Module version is `0.0.0-unstable-pre-1.0`. The package is private and is not listed in `pnpm-workspace.yaml`.

## Result flags that stay false

Every result forces `host_contacted`, `verified_on_host`, `live_customer_authority`, `external_identity_created`, `credential_created`, `identity_authenticated`, `vantio_sufficient`, `active_set_by_enterprise_writer`, and `satisfies_host_proof` to false. `APPROVED` means the record rule was satisfied. It does not mean a host attached, a freeze ran, or a council passed.
