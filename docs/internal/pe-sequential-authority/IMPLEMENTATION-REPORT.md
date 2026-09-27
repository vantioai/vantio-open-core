# Implementation report

INTERNAL_CANDIDATE | EVALUATE_ONLY | NOT_HOST_ENFORCEMENT | NOT_SHIPPED | NO_KERNEL | NO_ENROLL | NO_CREDENTIAL_MATERIAL | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

Producer classification before council: `PE_SEQUENTIAL_AGGREGATE_AUTHORITY_READY_FOR_COUNCIL`

This classification means the branch is ready for a separate council. It is a producer handoff. It is not a merge and it does not attach enforcement on a host.

## Revision

Council `bc-d04c35dd-3f9d-5599-ab0b-5b238e7c83c7` returned `PE_SEQUENTIAL_AGGREGATE_AUTHORITY_NEEDS_REVISION` on tip `403f4b06d4a2eac9ca98da0573f13674fc982375`.

This revision's classification before the next council is `PE_SEQUENTIAL_AGGREGATE_AUTHORITY_REVISION_READY_FOR_COUNCIL`. That is a producer handoff. It is not a council verdict and it is not a merge.

The catalog entry for the subject envelope is authoritative for revocation. A caller-held `ACTIVE` copy is denied when that catalog entry is `REVOKED`, including when the ledger has no mark. Ancestor `REVOKED` catalog entries and ledger marks still deny.

Parent generation drift denies when `issued_against_parent_generation` differs from the catalog parent generation. The drift check is not limited to parent state `ACTIVE`. A child issued against generation 0 is denied when the catalog parent is `EXPIRED` at generation 4. A `REVOKED` parent still denies through the ancestor revocation check, including when that parent's generation has also moved.

`evaluate` of `revoke_grant` still returns `revoke_transition` only. `revoke` still writes the mark. `host_attachment` stays false. `enforcement` stays `EVALUATE_ONLY`. `doctrine_present` stays false. Shared-family lineage ceilings are unchanged: a different `principal_id` keeps its own `resource_budget` counter, and the lineage ceiling stays shared.

Re-run of `node --test tests/pe-sequential-authority/*.test.cjs` on this revision reports 36 tests and 0 failures. The two adversarial cases cover a stale `ACTIVE` subject against a `REVOKED` catalog entry with an empty ledger, and parent generation drift when the catalog parent is `EXPIRED` at generation 4.

Producer: `bc-9eb86d6c-ac94-528a-8d98-23f58f64ad38`

Producer URL: https://cursor.com/agents/bc-9eb86d6c-ac94-528a-8d98-23f58f64ad38

Starting commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`

## What landed

Private package `@vantio/pe-sequential-authority` at `0.0.0-unstable-pre-1.0`. The version matches the unstable posture. It is not a bump of CLI `0.3.24`, Node SDK `0.2.4`, or Python `3.1.0`.

`evaluate`, `proposeDelegation`, and `revoke` are pure. Results keep `host_attachment` false and `doctrine_present` false.

The production-readiness registry on main is unchanged. This candidate does not edit it.

## Checks

From the repository root:

```sh
node --test tests/pe-sequential-authority/*.test.cjs
```

The producer run of that command reported 32 tests and 0 failures. The suite covers the nine invariants, the twelve limit axes, empty-list rejection, revocation of a copied descendant, and isolation from the CLI, the Python SDK, and the workspace file.

`node docs/scripts/check-docs-release.mjs` reports one failure: `legacy-stale-name-inventory-frozen` names `tests/shared-health-vocabulary/collision.test.cjs`. That file arrived in `c1de025` and is on the starting commit. This candidate does not edit the frozen inventory.

## Hard-stop attestations

- CLI, Python SDK, and Node SDK bytes are unchanged. No version bump.
- No kernel program, enroll path, socket, or credential material.
- No publish, tag, announcement, or customer deploy.
- No Phantom Engine customer-manual body copied onto this branch.
- Draft pull request only. Not merged.
- Council is a separate agent. This producer did not run it.
