# Independent council

Audience: INTERNAL_RESTRICTED

Status: `PENDING_INDEPENDENT_COUNCIL`

Producer classification under review: `BENCHMARK_FRAMEWORK_READY_FOR_COUNCIL`

This file is the producer stub. The planning producer does not sit the council and does not write a verdict.

## 1. What a separate council reviews

| Item | Value |
| --- | --- |
| Repository | `vantioai/vantio-open-core` |
| Directory | `docs/planning/benchmark-framework/` |
| Base named by the producer | `89f95099d0dce463307eb75d78e7fcf2ef99feb2` |
| Producer | `bc-e0913dd4-07fa-5610-a4fe-8178e8f2b6b6` |
| Classification the producer claims | `BENCHMARK_FRAMEWORK_READY_FOR_COUNCIL` |

## 2. Seats

| Seat | Scope | Verdict |
| --- | --- | --- |
| 1 | Seven stages are present in order, and a later stage is not `SATISFIED` while an earlier stage is `NOT_REACHED` | `UNSAT` |
| 2 | Lineup checkmarks stay at `DOES_NOT_SATISFY_ANY_STAGE` | `UNSAT` |
| 3 | Each dimension is scored from a cited document, including documented absence | `UNSAT` |
| 4 | Every performance metric is `NOT_MEASURED`, with no estimated number | `UNSAT` |
| 5 | Private Phantom Engine bodies are not copied | `UNSAT` |
| 6 | Closed actions in `00-PROGRAM-BOUNDARY.md` stayed closed | `UNSAT` |

## 3. Checks the council can re-run

From the repository root:

`node --test docs/planning/benchmark-framework/scripts/check-framework.test.mjs`

The diff is limited to `docs/planning/benchmark-framework/`.

`BENCHMARK-MANIFEST.json` has `merge` false, `council_verdict` null, and `pe_confidential_copied` false.

No cell has `current_stage` `EVIDENCE_BACKED_BEST_IN_CLASS`.

## 4. Verdict block

| Field | Value |
| --- | --- |
| Council agent | `UNSAT` |
| Reviewed tip | `UNSAT` |
| Verdict | `PENDING_INDEPENDENT_COUNCIL` |
| Blocking findings | `UNSAT` |
