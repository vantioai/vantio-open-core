# PKG-02 reader compatibility entry gates — architecture council notes

PRIVATE | INERT | NOT SHIPPED | READ_AND_EXPLAIN | NO_WRITE_BACK | NO_LIVE_WRITER | NO_MIGRATION | NO_STABLE_SCHEMA

Audience: INTERNAL_RESTRICTED

These notes are the architecture record for this producer packet. They are not a council verdict. `council_verdict` in the gate report stays null. A later council agent accepts or rejects the packet.

Starting commit: `89f95099d0dce463307eb75d78e7fcf2ef99feb2`.

## 1. Decision

Prove eleven reader gates on the merged Unit F reader before any Unit D or Unit E work. The proof is an inert evaluator plus direct and adversarial tests. Passing the proof classifies the packet `OPTICS_PKG02_READER_COMPAT_GATES_READY_FOR_COUNCIL`. Passing it does not authorize a writer, a version bump, or a merge.

## 2. Why the gates sit in front of the writers

`docs/planning/optics-pkg02/06-RELEASE-AND-ROLLBACK-BOUNDARY.md` makes Unit D depend on A, B, and F, and Unit E depend on A, C, and F. Both release gates also require that CLI `0.3.24` is not treated as the reader of a future file. Shipping either writer first would publish a record the frozen CLI labels `SUCCESS` for every call row.

The entry gates make that pairing explicit and fail closed. They do not patch `displayCall`.

## 3. Reader under test

The evaluator calls `readRunFile` from `@vantio/optics-record-reader`. That function reads bytes, explains a copy through the Unit B adapter, and reads the same path again. The evaluator does not reimplement the contract mapper and does not import `@vantio/cli`.

Tests pass in the frozen `displayCall` result as an oracle. The package itself does not load the CLI. If that oracle returns anything other than optics `SUCCESS` for the future call, the frozen-CLI gate fails. This force will not treat a changed CLI as if `0.3.24` had grown an honest future reader.

## 4. Gate dispositions

| Gate | Matrix class recorded on the proof | Pass condition |
| --- | --- | --- |
| Mixed-version directories | `PARTIAL` | A CLI `0.3.24` file, a Python `3.1.0` file, and a future canonical file stay side by side. Their bytes stay distinct and unchanged. |
| Legacy records | `REQUIRES_ADAPTER` | Both legacy files keep `schema_version` `2` and `vantio_run_log` `"1"`. The reading origin is `LEGACY_UNMARKED`. Python stored optics `SUCCESS` is refused. |
| Future records | `REQUIRES_ADAPTER` for the inert reader, frozen pairing `UNSUPPORTED` | Explicit `OBSERVED` with producer and version stays `OBSERVED` and `LOCAL_OBSERVATION`. Workload `SUCCESS` stays on `application_status`. |
| Unknown statuses | `REJECT_WITH_EXPLANATION` | An unknown optics token is class `unknown`, display `UNAVAILABLE`, `optimistic_default_forbidden`. The raw token is not echoed. |
| Absent fields | `PARTIAL` | Missing optics, HTTP status, bytes, and application status stay absent. Missing optics becomes `UNAVAILABLE`, not `OBSERVED`. |
| Origin preservation | `READ_ONLY` | `IMPORTED` keeps `original_evidence_origin`. A claimed local origin without provenance stays `LEGACY_UNMARKED`. Demo host `optics-demo.invalid` stays `SIMULATED_DEMO` on that observation. Provenanced `LOCAL_OBSERVATION` stays. |
| Reader fallback | `UNSUPPORTED` as the frozen outcome, disposition `NON_WRITING_FALLBACK` | Newer `schema_version` `99` and `schema_status` `stable-v9` remain on disk. Corrupt input is `OPTICS_ERROR`. A missing path is `UNAVAILABLE` / `ABSENT_FILE` and is not created. |
| No unknown to SUCCESS | `REJECT_WITH_EXPLANATION` | No evaluated explanation displays optics `SUCCESS`. Application `SUCCESS` is not copied into `optics_status`. |
| Frozen CLI honestly unsupported | `UNSUPPORTED` | `displayCall` on the future record still returns optics `SUCCESS`. The gate names that pairing unsupported. Node SDK `0.2.4` ingest does not become a local record. |
| Rollback without record rewriting | `UNSUPPORTED` | After a refused write, activate, and migrate option, the future file and the newer-schema file are still the same bytes, with origin and schema marker intact. |
| Reader refuses unsafe promotion | `READ_ONLY` | `promote` does not upgrade origin and does not rewrite bytes. Prohibited names and a secret canary are not echoed. |

`achievement` on every gate stays `NOT_SHIPPED`.

## 5. Fallback is not a migration

A newer on-disk schema is explained on a detached copy. That copy uses contract `schema_version` `0` and `schema_status` `unstable-pre-1.0`, which is the current contract rule. The source file is not rewritten to those values. The gate report keeps the source `schema_version` and `schema_status` so a rollback notice can still show the marker the file carries.

The frozen CLI cannot show that marker. Its display result is optics `SUCCESS` for a call row. The honest disclosure for that binary is `UNSUPPORTED`.

## 6. What a pass does not decide

- It does not select `PKG02-FUTURE-CLI-UNASSIGNED` or `PKG02-FUTURE-PYTHON-UNASSIGNED` as real versions.
- It does not satisfy the Unit D ordinary-client proof that still has to run on a machine with CLI `0.3.24` installed beside a future CLI. No future CLI exists in this force.
- It does not resolve Founder decision 6. No reader path stamps `LEGACY_UNMARKED` as `LOCAL_OBSERVATION`.
- It does not change fail-open for the workload. The evaluator never sees a caller return value to rewrite.
- It does not merge this pull request.

## 7. Fail closed

A missing role, a symlink, a name that leaves the directory, a missing frozen-display oracle, a rewritten byte, or any optics `SUCCESS` in an explanation yields `OPTICS_PKG02_READER_COMPAT_GATES_BLOCKED`. The ready token is not also present on that report. `units_d_e` remains `NOT_AUTHORIZED` in both outcomes.

## 8. Council question

The question for the independent council is whether these eleven proofs are sufficient entry evidence before a later force may start Unit D or Unit E. This producer does not sit that council.
