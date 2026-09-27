# Enterprise E1–E3 implementation report

Audience: INTERNAL_RESTRICTED

Producer classification: `ENTERPRISE_E1_E3_INTERNAL_READY_FOR_COUNCIL`

Producer: `bc-c9b05a34-636c-589b-987b-4ea94e4f8c4c` at https://cursor.com/agents/bc-c9b05a34-636c-589b-987b-4ea94e4f8c4c

Model: Grok 4.7. This producer did not sit the council and did not mark the pull request ready.

## What landed

Private module `@vantio/enterprise-governance-internal` at `0.0.0-unstable-pre-1.0` under `internal/enterprise-governance/`. It is not in `pnpm-workspace.yaml`. It does not change `@vantio/cli` `0.3.24`, `vantio-agent-sdk` `3.1.0`, or the other published manifests.

The plan packet under `docs/planning/enterprise-governance/` is byte-identical to the hashes in `GOVERNANCE-MANIFEST.json`. Its council file is still pending. EG-D1 through EG-D10 remain unresolved. EG-D5 and EG-D6 were left on the defaults named in the plan: no host activation in this repository, and no store product selected.

## Checks

From the repository root:

```sh
node --test tests/enterprise-e1-e3/*.test.cjs
node docs/scripts/check-docs-release.mjs
```

The first producer run of the test command reported 32 tests and 0 failures. Direct tests cover founding, host intent, policy widen, grant window, narrow, recovery and freeze records, revocation, customer-held evidence, spawn, and inspect. Adversarial tests cover the rejected acts, self-approval, consensus, role labels, workload domains, redelegation, subset violations, child inheritance, writer sources, root-only acts, recovery ceiling, freeze, store outage, and prohibited fields. Isolation tests cover package paths, plan hashes, and the absence of network or host imports.

## Revision

Council `bc-6a9b9454-6006-513e-830b-47879601b121` returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on tip `2598d89c14085dcda280a574a372b5d81f28ae1f`. Revision producer: `bc-f6c05a63-83a5-5bd9-bcf6-ae26f1826380` at https://cursor.com/agents/bc-f6c05a63-83a5-5bd9-bcf6-ae26f1826380. This revision stays on draft pull request #100. Handoff token: `ENTERPRISE_E1_E3_INTERNAL_REVISION_READY_FOR_COUNCIL`. That token is not a council verdict and not host proof.

Record-layer changes:

- `not_before` closes exercise. An approved grant is `NOT_YET` with `can_exercise` false until the window, so a security grant does not narrow policy early. `noteSpawn` with `now` before `not_before` does not report parent egress or `within_subset: true`. A policy `WIDEN` with a future `not_before` is stored on `open_widens` and is written onto `root.policy` only when a clock enters the window.
- `ENDED` is sticky. A later clock before `not_before` does not become `NOT_YET`, and a clock back inside the window does not become `OPEN`. A grant whose `not_after` is already past is not left `OPEN`. Spawn without `now` on an ended grant returns `ROLLBACK_SCOPE_ONLY`. `host_expanded_authority_cleared` stays `UNSATISFIED`. EG-E2-8 remains `RECORD_LAYER_ONLY_HOST_UNSATISFIED`.
- A later root `NARROW` bounds existing grants. Spawn of a child outside the current customer envelope is refused with `within_subset: false`.

The revision run of `node --test tests/enterprise-e1-e3/*.test.cjs` reported 35 tests and 0 failures. The three new adversarial tests cover those holds. EG-D1 through EG-D10 stay unresolved. EG-E3-7, EG-E3-8, EG-SUB-6, and EG-SP-1 through EG-SP-5 stay host-unsatisfied. `verified_on_host` stays false. No live customer authority was created.

`node docs/scripts/check-docs-release.mjs` fails `legacy-stale-name-inventory-frozen` on this branch and on starting commit `89f95099d0dce463307eb75d78e7fcf2ef99feb2`. The only named file is `tests/shared-health-vocabulary/collision.test.cjs`, which this force does not edit. The other release checks passed. This branch adds no stale-name file.

## Hard-stop attestations

- No live customer authority, credential, or external identity.
- No host contact. `verified_on_host` is false on every result.
- No second enforcement engine, enroll command, or kernel loader.
- No CLI, Python, workflow, or `docs/governance/` change.
- No plan-packet edit. Plan council was not marked passed.
- EG-SP-1 through EG-SP-5 were not run. EG-E3-8 and EG-SUB-6 stay host-unsatisfied.
- Schema stays `unstable-pre-1.0`.
- Draft pull request only. Not merged.
