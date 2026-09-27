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

## Composition revision

Council `bc-fb458789-7599-5abb-a10f-ccc17f25ead3` returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on tip `db70e93bca42d7d5be56b2afaed4d1c95a24cf24`. Revision producer: `bc-03d7917b-2c1d-55c3-bbe9-33637a05f4f7` at https://cursor.com/agents/bc-03d7917b-2c1d-55c3-bbe9-33637a05f4f7. This revision stays on draft pull request #100. Handoff token: `ENTERPRISE_E1_E3_INTERNAL_REVISION_READY_FOR_COUNCIL`. That token is not a council verdict and not host proof.

Record-layer changes:

- A deferred widen applies by composing the authority it added, relative to the policy at approval, onto the policy in force. A later root narrow to `read`, spend 15, and path constraints `p1` and `p2` stays in force when the window opens. The child `connect` / spend 50 stays `within_subset: false`. After the widen window, that narrow is still the policy.
- Two deferred widens from the same baseline, one adding destination `d2` and one raising spend to 80, both apply at window entry. The same second widen issued after an immediate first widen stays `NOT_A_PURE_WIDEN`.
- A recorded freeze still returns `FREEZE_RECORDED` for a later grant, and `noteClock` into the deferred window leaves spend and destinations unexpanded.
- While the store is unavailable, `proposeGrant` returns `STORE_UNAVAILABLE_NO_WIDEN`, and `noteClock` into the deferred window leaves policy version, spend, and destinations unchanged.
- A policy widen whose `not_after` is already past is `POLICY_WIDEN_ENDED` with `policy_applied: false`. Spend and destinations stay at the current policy, including when a later clock is placed inside that past window.

The isolated `not_before`, sticky `ENDED`, and later-`NARROW` holds stay closed. The composition run of `node --test tests/enterprise-e1-e3/*.test.cjs` reported 40 tests and 0 failures. EG-D1 through EG-D10 stay unresolved. EG-E2-8 stays `RECORD_LAYER_ONLY_HOST_UNSATISFIED`. `verified_on_host` stays false. No live customer authority was created. CLI `0.3.24` and Python `3.1.0` are unchanged.

## Sibling revision

Council `bc-9e4306a5-2874-5ae1-ba2e-c6aadfd1ba5b` returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on tip `73f291b009f4b0d223c5003385f38973a3a5e8b1`. Revision producer: `bc-80600242-87e1-5cba-b975-527b8c52e798` at https://cursor.com/agents/bc-80600242-87e1-5cba-b975-527b8c52e798. This revision stays on draft pull request #100. Handoff token: `ENTERPRISE_E1_E3_INTERNAL_REVISION_READY_FOR_COUNCIL`. That token is not a council verdict and not host proof.

Record-layer changes:

- A later narrow that sets spend or size between the approval baseline and the stored widen target stays. `noteClock` inside the deferred window does not raise that cap to the stored target.
- A destination a later narrow removes is not treated as an addition still owed by an earlier deferred widen. The cut holds when the narrow lands before the window, and when it lands while the window is open, including clock-back before `not_before` and re-entry. The scripted narrow (`read`, spend 15, paths `p1` and `p2`) still holds through entry, clock-back, and expiry. `d2` still returns on re-entry when that narrow did not remove it.
- When one deferred widen expires, or a clock moves before its start, siblings whose windows still contain the clock are composed again. The leaving entry's rollback is not applied as the whole policy. A spend approval that runs longer than a destination approval stays at 80 after the destination window ends, and the symmetric case keeps `d2`. A clock from April back to February drops a spend widen that has not started and leaves `d2` in place.

Holds C–E stay closed. A freeze still leaves pending widens unapplied after a later narrow. A store outage still leaves policy version, spend, and destinations unchanged, including an already-applied widen. A widen whose window has already ended stays `POLICY_WIDEN_ENDED` with `policy_applied: false`.

The sibling run of `node --test tests/enterprise-e1-e3/*.test.cjs` reported 48 tests and 0 failures. EG-D1 through EG-D10 stay unresolved. EG-E2-8 stays `RECORD_LAYER_ONLY_HOST_UNSATISFIED`. `verified_on_host` stays false. No live customer authority was created. CLI `0.3.24` and Python `3.1.0` are unchanged.

## Ceiling revision

Council `bc-3cc20d59-8923-5424-b1ba-ac17db02854a` returned `ENTERPRISE_E1_E3_INTERNAL_NEEDS_REVISION` on tip `34a1d2ad1007e573cc1fac137f334b2acb5c3a33`. Revision producer: `bc-d63660c7-e8e6-55e6-96dd-3d7f69c3241b` at https://cursor.com/agents/bc-d63660c7-e8e6-55e6-96dd-3d7f69c3241b. This revision stays on draft pull request #100. Handoff token: `ENTERPRISE_E1_E3_INTERNAL_REVISION_READY_FOR_COUNCIL`. That token is not a council verdict and not host proof.

Record-layer change:

- `composeCap` keeps a live cap that is already above the ceiling recorded on an older open widen. It does not restore that widen's stored target. An immediate widen to spend 90, a root narrow to 70, and a later immediate widen to 85 stay at 85 on `noteClock`. The same shape for size stays at 75. With a deferred spend-80 window still open, a later approval of 75 survives the January clock. A March clock that drops an expired `d2` leaves spend at 75. The recorded ceiling on the older widen stays 70.

Holds A–E stay closed. The isolated `not_before`, sticky `ENDED`, and later-`NARROW` holds stay closed. A cap equal to the recorded ceiling still stays there, including the scripted narrow to spend 70 and the sibling expiry that keeps spend 80 after `d2` drops.

The ceiling run of `node --test tests/enterprise-e1-e3/*.test.cjs` reported 52 tests and 0 failures. EG-D1 through EG-D10 stay unresolved. EG-E2-8 stays `RECORD_LAYER_ONLY_HOST_UNSATISFIED`. `verified_on_host` stays false. No live customer authority was created. CLI `0.3.24` and Python `3.1.0` are unchanged.

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
